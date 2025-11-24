from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .config import get_settings
from .llm import LLMClient, LLMMessage
from .messaging import publish_stage_event, send_queue_message
from .storage import BlobStore


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
    normalized = _normalize_source_text(source)
    prompt = (
        "Please reformat the following PlantUML code so that:\n"
        "- Line breaks inside element names are removed\n"
        "- Arrow labels stay on a single line\n"
        "- Indentation is consistent\n"
        "- All elements (actors, participants, lifelines, states, etc.) are clearly defined\n"
        "- The diagram remains functionally identical\n"
        "Return only the fixed PlantUML without additional commentary or fences."
    )
    messages = [
        LLMMessage("system", "You are an assistant that cleans and formats PlantUML diagrams."),
        LLMMessage("user", f"{prompt}\n\n<plantuml>\n{normalized}\n</plantuml>"),
    ]
    try:
        model = os.getenv("DOCWRITER_PLANTUML_REFORMAT_MODEL", "gpt-5")
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
        raise
        return normalized


def _render_with_plantuml(source: str | bytes, fmt: str) -> bytes:
    import requests

    server_url = os.getenv("PLANTUML_SERVER_URL")
    if not server_url:
        raise DiagramRenderError("PLANTUML_SERVER_URL not configured")

    uml_source = _reformat_plantuml_text(source)
    endpoint = f"{server_url.rstrip('/')}/{fmt}"

    try:
        response = requests.post(
            endpoint,
            data=uml_source.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"PlantUML rendering failed: {exc}") from exc


def process_diagram_render(data: Dict[str, Any]) -> None:
    """Render a PlantUML diagram request."""
    settings = get_settings()
    job_id = data.get("job_id")
    if not job_id:
        raise DiagramRenderError("diagram render payload missing job_id")

    if "diagram_requests" in data:
        finalize_payload = data.get("finalize_payload") or {}
        code_blocks = finalize_payload.get("diagram_code_blocks") if isinstance(finalize_payload, dict) else {}
        requests = data.get("diagram_requests", [])
        if not isinstance(requests, list):
            raise DiagramRenderError("diagram_requests payload must be a list")
        try:
            store = BlobStore()
            results: List[Dict[str, Any]] = []
            for request in requests:
                diag_id = request.get("diagram_id") or str(uuid4())
                fmt = _normalize_format(request.get("format"))
                blob_path = request.get("blob_path") or f"jobs/{job_id}/images/{diag_id}.{fmt}"
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
                content = _render_with_plantuml(formatted_source, fmt)
                store.put_bytes(blob=blob_path, data_bytes=content)
                relative_path = blob_path
                prefix = f"jobs/{job_id}/"
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
            send_queue_message(settings.sb_queue_finalize_ready, payload)
            publish_stage_event("DIAGRAM", "DONE", payload)
            publish_stage_event("FINALIZE", "QUEUED", payload)
        except DiagramRenderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise DiagramRenderError(f"unexpected rendering error: {exc}") from exc
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
        blob_path = data.get("blob_path") or f"jobs/{job_id}/images/{diagram_id}.{fmt}"
        (store or BlobStore()).put_bytes(blob=blob_path, data_bytes=content)
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"unexpected rendering error: {exc}") from exc
