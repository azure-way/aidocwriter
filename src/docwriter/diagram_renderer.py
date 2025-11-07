from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .config import get_settings
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


def _normalize_source_text(source: str) -> str:
    if not isinstance(source, str):
        return "@startuml\n@enduml"
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\\n", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    trimmed = "\n".join(lines).strip()
    if not trimmed.lower().startswith("@startuml"):
        trimmed = "@startuml\n" + trimmed
    if not trimmed.lower().endswith("@enduml"):
        if not trimmed.endswith("\n"):
            trimmed += "\n"
        trimmed += "@enduml"
    return trimmed


def _render_with_plantuml(source: str | bytes, fmt: str) -> bytes:
    import requests

    server_url = os.getenv("PLANTUML_SERVER_URL")
    if not server_url:
        raise DiagramRenderError("PLANTUML_SERVER_URL not configured")

    normalized = server_url.rstrip("/")
    endpoint = f"{normalized}/{fmt}"
    if isinstance(source, bytes):
        payload_bytes = source
    else:
        uml_source = _normalize_source_text(source)
        payload_bytes = uml_source.encode("utf-8")

    try:
        response = requests.post(
            endpoint,
            data=payload_bytes,
            headers={"Content-Type": "application/octet-stream"},
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"PlantUML rendering failed: {exc}") from exc


def process_diagram_render(data: Dict[str, Any]) -> None:
    """
    Render a PlantUML diagram request.

    Expected payload examples:

    Batch request:
    {
        "job_id": "...",
        "diagram_requests": [
            {
                "diagram_id": "diagram_1",
                "source": "@startuml ... @enduml",
                "format": "png",
                "code_block": "```plantuml ...```",
                "blob_path": "jobs/<job>/images/diagram_1.png"
            },
            ...
        ],
        "finalize_payload": { ... }
    }

    Single request (debugging/CLI):
    {
        "job_id": "...",
        "diagram_id": "diagram_1",
        "source": "@startuml ... @enduml",
        "format": "png",
        "blob_path": "jobs/<job>/images/diagram_1.png"
    }
    """

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
                    source_bytes = store.get_bytes(source_path)
                except Exception as exc:
                    raise DiagramRenderError(f"failed to load diagram source for {diag_id}: {exc}") from exc
                content = _render_with_plantuml(source_bytes, fmt)
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
    if source_path:
        try:
            store = BlobStore()
            source_bytes = store.get_bytes(source_path)
        except Exception as exc:
            raise DiagramRenderError(f"failed to load diagram source: {exc}") from exc
    else:
        source = data.get("source") or data.get("diagram_source")
        if not source:
            raise DiagramRenderError("diagram render payload missing source")
        source_bytes = None

    diagram_id = data.get("diagram_id") or str(uuid4())
    fmt = _normalize_format(data.get("format"))

    if not source:
        raise DiagramRenderError("diagram render payload missing source")

    try:
        payload = source_bytes if source_bytes is not None else source
        content = _render_with_plantuml(payload, fmt)
        blob_path = data.get("blob_path") or f"jobs/{job_id}/images/{diagram_id}.{fmt}"
        store = BlobStore()
        store.put_bytes(blob=blob_path, data_bytes=content)
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"unexpected rendering error: {exc}") from exc
