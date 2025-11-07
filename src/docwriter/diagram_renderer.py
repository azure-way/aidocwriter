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


def _render_with_plantuml(source: str, fmt: str) -> bytes:
    import requests

    server_url = os.getenv("PLANTUML_SERVER_URL")
    if not server_url:
        raise DiagramRenderError("PLANTUML_SERVER_URL not configured")

    try:
        response = requests.post(
            f"{server_url.rstrip('/')}/{fmt}",
            data=source,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"PlantUML rendering failed: {exc}")



def process_diagram_render(data: Dict[str, Any]) -> None:
    """
    Render a PlantUML diagram request.
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
            payload_source: str | bytes = store.get_bytes(source_path)
        except Exception as exc:
            raise DiagramRenderError(f"failed to load diagram source: {exc}") from exc
    else:
        source = data.get("source") or data.get("diagram_source")
        if not source:
            raise DiagramRenderError("diagram render payload missing source")
        payload_source = source

    diagram_id = data.get("diagram_id") or str(uuid4())
    fmt = _normalize_format(data.get("format"))

    try:
        content = _render_with_plantuml(payload_source, fmt)
        blob_path = data.get("blob_path") or f"jobs/{job_id}/images/{diagram_id}.{fmt}"
        store = BlobStore()
        store.put_bytes(blob=blob_path, data_bytes=content)
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"unexpected rendering error: {exc}") from exc
