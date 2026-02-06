from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4

from .config import get_settings
from .llm import LLMClient, LLMMessage
from .messaging import publish_stage_event, send_queue_message
from .storage import BlobStore, JobStoragePaths
from .telemetry import track_exception
from .plantuml_reference import PLANTUML_REFERENCE_TEXT


class DiagramRenderError(RuntimeError):
    """Raised when diagram rendering fails."""


def _normalize_format(fmt: Optional[str]) -> str:
    if not fmt:
        return "png"
    fmt = fmt.lower().strip()
    if fmt in {"png", "svg"}:
        return fmt
    return "png"


def _normalize_source_text(source: str | bytes) -> str:
    if isinstance(source, bytes):
        text = source.decode("utf-8-sig", errors="replace")
    else:
        text = source
    text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    stripped = text.strip()
    if not stripped.lower().startswith("@startuml"):
        stripped = "@startuml\n" + stripped
    if not stripped.lower().endswith("@enduml"):
        stripped = stripped + ("\n" if not stripped.endswith("\n") else "") + "@enduml"
    if not stripped.endswith("\n"):
        stripped += "\n"
    return stripped


def _remove_markdown_fences(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _preclean_plantuml_text(source: str | bytes) -> str:
    """Deterministic cleanup to strip Markdown fences and normalize PlantUML blocks."""
    text = source.decode("utf-8-sig", errors="replace") if isinstance(source, bytes) else str(source)
    text = _strip_code_fences(text)
    text = _remove_markdown_fences(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _normalize_source_text(text)
    return text


_reformat_llm_client: Optional[LLMClient] = None


def _get_reformat_client() -> LLMClient:
    global _reformat_llm_client
    if _reformat_llm_client is None:
        settings = get_settings()
        _reformat_llm_client = LLMClient(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            api_version=settings.openai_api_version or "2024-08-01-preview",
            use_responses=True,
        )
    return _reformat_llm_client


def _regenerate_from_description(
    diagram_id: str,
    description: str | None,
    diagram_type: str | None,
    entities: List[str] | None,
    relationships: List[str] | None,
) -> Optional[str]:
    """Attempt to rebuild PlantUML from a description when rendering failed twice."""
    if not description:
        return None
    settings = get_settings()
    client = _get_reformat_client()
    sys = (
        "You are a PlantUML fixer. Given a description and optional entities/relationships, produce a minimal,"
        " valid PlantUML diagram. Do not return Markdown fences. Include exactly one @startuml and one @enduml."
        " Prefer simple shapes and arrows that match the description. Keep labels short and on one line."
    )
    parts = [
        f"Diagram id: {diagram_id}",
        f"Description: {description}",
    ]
    if diagram_type:
        parts.append(f"Diagram type hint: {diagram_type}")
    if entities:
        parts.append(f"Entities: {', '.join(entities)}")
    if relationships:
        parts.append(f"Relationships: {', '.join(relationships)}")
    parts.append("PlantUML reference (use for syntax choices only):")
    parts.append(PLANTUML_REFERENCE_TEXT)
    prompt = "\n".join(parts)
    try:
        text = client.chat(
            model=settings.writer_model,
            messages=[LLMMessage("system", sys), LLMMessage("user", prompt)],
        )
    except Exception as exc:  # pragma: no cover - defensive
        track_exception(exc, {"stage": "DIAGRAM_RENDER", "operation": "regenerate_from_description"})
        return None
    try:
        return _reformat_plantuml_text(text)
    except Exception:
        return None


def _strip_code_fences(text: str) -> str:
    if "```" not in text:
        return text
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def _reformat_plantuml_text(source: str | bytes) -> str:
    normalized = _preclean_plantuml_text(source)
    prompt = (
        "Please fix the following PlantUML code so that:\n"
        "- The diagram compiles without errors\n"
        "- Line breaks inside element names are removed\n"
        "- Arrow labels stay on a single line\n"
        "- Indentation is consistent\n"
        "- All elements (actors, participants, lifelines, states, etc.) are clearly defined\n"
        "- The diagram remains functionally identical\n"
        "- Do not convert to Mermaid or any other format\n"
        "Return only the fixed PlantUML without additional commentary or fences."
    )
    messages = [
        LLMMessage("system", "You are an assistant that fix, clean and formats PlantUML diagrams."),
        LLMMessage("user", f"{prompt}\n\n<plantuml>\n{normalized}\n</plantuml>"),
    ]
    try:
        model = os.getenv("DOCWRITER_PLANTUML_REFORMAT_MODEL", "gpt-5.1")
        client = _get_reformat_client()
        result = client.chat(model=model, messages=messages)
        if isinstance(result, dict):
            formatted = result.get("plantuml") or ""
        else:
            formatted = _strip_code_fences(str(result))
        formatted = formatted.strip()
        if not formatted:
            return normalized
        formatted = _normalize_source_text(formatted)
        return formatted
    except Exception:
        return normalized


def _render_with_plantuml(
    source: str | bytes,
    fmt: str,
    *,
    regen_after_second_failure: Optional[Callable[[], str | None]] = None,
) -> bytes:
    import requests

    server_url = os.getenv("PLANTUML_SERVER_URL")
    if not server_url:
        raise DiagramRenderError("PLANTUML_SERVER_URL not configured")

    last_exc: Exception | None = None
    last_source = source
    for attempt in range(3):
        try:
            uml_source = _reformat_plantuml_text(last_source)
            last_source = uml_source
            endpoint = f"{server_url.rstrip('/')}/{fmt}"

            response = requests.post(
                endpoint,
                data=uml_source.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=30,
            )

            response.raise_for_status()
            return response.content
        except Exception as exc:  # pragma: no cover - defensive
            last_exc = exc
            track_exception(exc, {"stage": "DIAGRAM_RENDER", "attempt": str(attempt + 1)})
            if regen_after_second_failure and attempt == 0:
                try:
                    regenerated = regen_after_second_failure()
                    if regenerated:
                        last_source = regenerated
                        continue
                except Exception as regen_exc:  # pragma: no cover - defensive
                    track_exception(
                        regen_exc,
                        {"stage": "DIAGRAM_RENDER", "attempt": "regen_after_second_failure"},
                    )
    track_exception(last_exc or Exception("PlantUML unknown failure"), {"stage": "DIAGRAM_RENDER"})
    raise DiagramRenderError(f"PlantUML rendering failed after 3 attempts: {last_exc}") from last_exc


def process_diagram_render(data: Dict[str, Any]) -> None:
    """Render a PlantUML diagram request."""
    settings = get_settings()
    job_id = data.get("job_id")
    if not job_id:
        raise DiagramRenderError("diagram render payload missing job_id")
    user_id = data.get("user_id")
    if not user_id:
        raise DiagramRenderError(f"diagram render payload missing user_id for job {job_id}")
    job_paths = JobStoragePaths(user_id=user_id, job_id=job_id)

    if "diagram_requests" in data:
        finalize_payload = data.get("finalize_payload") or {}
        code_blocks = finalize_payload.get("diagram_code_blocks") if isinstance(finalize_payload, dict) else {}
        plan_specs = {}
        try:
            plan_specs = {
                spec.get("diagram_id"): spec
                for spec in (finalize_payload.get("plan") or {}).get("diagram_specs", [])
                if isinstance(spec, dict) and spec.get("diagram_id")
            }
        except Exception:
            plan_specs = {}
        requests = data.get("diagram_requests", [])
        if not isinstance(requests, list):
            raise DiagramRenderError("diagram_requests payload must be a list")
        try:
            store = BlobStore()
            total_requested = len(requests)
            start_message = (
                f"Rendering {total_requested} diagram{'s' if total_requested != 1 else ''}"
                if total_requested
                else "Rendering diagrams"
            )
            publish_stage_event(
                "DIAGRAM",
                "START",
                finalize_payload or {"job_id": job_id, "user_id": user_id},
                extra={"message": start_message},
            )
            results: List[Dict[str, Any]] = []
            for request in requests:
                diag_id = request.get("diagram_id") or str(uuid4())
                fmt = _normalize_format(request.get("format"))
                blob_path = request.get("blob_path") or job_paths.images(f"{diag_id}.{fmt}")
                source_path = request.get("source_path")
                if not source_path:
                    raise DiagramRenderError(f"diagram {diag_id} missing source_path")
                try:
                    source_text = store.get_text(source_path)
                except Exception as exc:
                    raise DiagramRenderError(f"failed to load diagram source for {diag_id}: {exc}") from exc
                formatted_source = _reformat_plantuml_text(source_text)
                if formatted_source != source_text:
                    store.put_text(source_path, formatted_source)
                spec = plan_specs.get(diag_id) or {}
                regen_fn = None
                description = spec.get("plantuml_prompt") or spec.get("description")
                if description:
                    entities = spec.get("entities") if isinstance(spec.get("entities"), list) else None
                    relationships = spec.get("relationships") if isinstance(spec.get("relationships"), list) else None
                    regen_fn = lambda desc=description, dtype=spec.get("diagram_type"), ent=entities, rel=relationships, did=diag_id: _regenerate_from_description(
                        did, desc, dtype, ent, rel
                    )
                content = _render_with_plantuml(formatted_source, fmt, regen_after_second_failure=regen_fn)
                store.put_bytes(blob=blob_path, data_bytes=content)
                relative_path = blob_path
                prefix = f"{job_paths.root}/"
                if blob_path.startswith(prefix):
                    relative_path = blob_path[len(prefix) :]
                code_block_map = code_blocks if isinstance(code_blocks, dict) else {}
                results.append(
                    {
                        "diagram_id": diag_id,
                        "blob_path": blob_path,
                        "relative_path": relative_path,
                        "code_block": code_block_map.get(diag_id),
                        "format": fmt,
                        "alt_text": request.get("alt_text"),
                    }
                )
            payload = {**finalize_payload, "diagram_results": results}
            payload.setdefault("job_id", job_id)
            payload.setdefault("user_id", user_id)
            send_queue_message(settings.sb_queue_finalize_ready, payload)
            complete_message = f"Generated {len(results)} diagram{'s' if len(results) != 1 else ''}"
            publish_stage_event("DIAGRAM", "DONE", payload, extra={"message": complete_message})
            publish_stage_event("FINALIZE", "QUEUED", payload)
        except DiagramRenderError as exc:
            track_exception(exc, {"job_id": job_id, "stage": "DIAGRAM_RENDER"})
            error_message = f"Diagram rendering failed: {exc}"
            publish_stage_event(
                "DIAGRAM",
                "FAILED",
                {"job_id": job_id, "user_id": user_id},
                extra={"message": error_message},
            )
            try:
                fallback_results = []
                for request in requests:
                    diag_id = request.get("diagram_id") or str(uuid4())
                    fallback_results.append(
                        {
                            "diagram_id": diag_id,
                            "code_block": code_blocks.get(diag_id) if isinstance(code_blocks, dict) else None,
                            "alt_text": request.get("alt_text"),
                            "error": error_message,
                        }
                    )
                payload = {**finalize_payload, "diagram_results": fallback_results}
                payload.setdefault("job_id", job_id)
                payload.setdefault("user_id", user_id)
                send_queue_message(settings.sb_queue_finalize_ready, payload)
                publish_stage_event("FINALIZE", "QUEUED", payload)
            except Exception as finalize_exc:  # pragma: no cover - defensive
                track_exception(finalize_exc, {"job_id": job_id, "stage": "DIAGRAM_RENDER", "operation": "enqueue_finalize_after_failure"})
            return
        except Exception as exc:  # pragma: no cover - defensive
            track_exception(exc, {"job_id": job_id, "stage": "DIAGRAM_RENDER"})
            error_message = "Unexpected diagram rendering error"
            publish_stage_event(
                "DIAGRAM",
                "FAILED",
                {"job_id": job_id, "user_id": user_id},
                extra={"message": error_message},
            )
            try:
                fallback_results = []
                for request in requests:
                    diag_id = request.get("diagram_id") or str(uuid4())
                    fallback_results.append(
                        {
                            "diagram_id": diag_id,
                            "code_block": code_blocks.get(diag_id) if isinstance(code_blocks, dict) else None,
                            "alt_text": request.get("alt_text"),
                            "error": f"{error_message}: {exc}",
                        }
                    )
                payload = {**finalize_payload, "diagram_results": fallback_results}
                payload.setdefault("job_id", job_id)
                payload.setdefault("user_id", user_id)
                send_queue_message(settings.sb_queue_finalize_ready, payload)
                publish_stage_event("FINALIZE", "QUEUED", payload)
            except Exception as finalize_exc:  # pragma: no cover - defensive
                track_exception(finalize_exc, {"job_id": job_id, "stage": "DIAGRAM_RENDER", "operation": "enqueue_finalize_after_failure"})
            return
        return

    source_path = data.get("source_path")
    store: Optional[BlobStore] = None
    if source_path:
        try:
            store = BlobStore()
            payload_source = store.get_text(source_path)
        except Exception as exc:
            raise DiagramRenderError(f"failed to load diagram source: {exc}") from exc
    else:
        payload_source = data.get("source") or data.get("diagram_source")
        if not payload_source:
            raise DiagramRenderError("diagram render payload missing source")

    diagram_id = data.get("diagram_id") or str(uuid4())
    fmt = _normalize_format(data.get("format"))

    formatted_source = _reformat_plantuml_text(payload_source)
    if source_path and formatted_source != payload_source:
        (store or BlobStore()).put_text(source_path, formatted_source)
    content = _render_with_plantuml(formatted_source, fmt)

    try:
        blob_path = data.get("blob_path") or job_paths.images(f"{diagram_id}.{fmt}")
        (store or BlobStore()).put_bytes(blob=blob_path, data_bytes=content)
    except Exception as exc:  # pragma: no cover - defensive
        track_exception(exc, {"job_id": job_id, "stage": "DIAGRAM_RENDER"})
        raise DiagramRenderError(f"unexpected rendering error: {exc}") from exc
