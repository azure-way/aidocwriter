from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from uuid import uuid4

from .config import get_settings
from .messaging import send_queue_message
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

    domain  = os.getenv("CONTAINER_APP_ENVIRONMENT_DOMAIN")
    if not domain:
        raise DiagramRenderError("CONTAINER_APP_ENVIRONMENT_DOMAIN not configured")
    
    app_server_url = os.getenv("PLANTUML_SERVER_APP_NAME")
    if not app_server_url:
        raise DiagramRenderError("PLANTUML_SERVER_APP_NAME not configured")

    logging.debug("Using PlantUML server at %s.%s", app_server_url, domain)
    server_url = f"https://{app_server_url}.{domain}"

    normalized = server_url.rstrip("/")
    endpoint = f"{normalized}/{fmt}"

    try:
        response = requests.post(
            endpoint,
            data=source.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            timeout=30,
        )
        response.raise_for_status()
        return response.content
    except Exception as exc:  # pragma: no cover - defensive
        raise DiagramRenderError(f"PlantUML rendering failed: {exc}") from exc


def process_diagram_render(data: Dict[str, Any]) -> None:
    """
    Render a PlantUML diagram request.

    Expected payload:
    {
        "job_id": "...",
        "diagram_id": "...",           # optional
        "source": "...",               # PlantUML source text
        "format": "png" | "svg",       # optional (default png)
        "blob_path": "...",            # optional target blob path
        "result_queue": "...",         # optional queue to send completion payload
        "metadata": {...}              # optional passthrough data
    }
    """

    job_id = data.get("job_id")
    source = data.get("source") or data.get("diagram_source")
    if not job_id or not source:
        raise DiagramRenderError("diagram render payload missing job_id or source")

    diagram_id = data.get("diagram_id") or str(uuid4())
    fmt = _normalize_format(data.get("format"))
    result_queue = data.get("result_queue") or get_settings().sb_queue_diagram_results

    def _publish(payload: Dict[str, Any]) -> None:
        if not result_queue:
            return
        try:
            send_queue_message(result_queue, payload)
        except Exception:
            logging.exception("Failed to publish diagram render result for job %s", job_id)

    try:
        image_bytes = _render_with_plantuml(source, fmt)
        blob_path = data.get("blob_path") or f"jobs/{job_id}/images/{diagram_id}.{fmt}"
        store = BlobStore()
        store.put_bytes(blob=blob_path, data_bytes=image_bytes)
        result_payload: Dict[str, Any] = {
            "job_id": job_id,
            "diagram_id": diagram_id,
            "blob_path": blob_path,
            "format": fmt,
            "status": "completed",
        }
        if "metadata" in data:
            result_payload["metadata"] = data["metadata"]
        _publish(result_payload)
    except DiagramRenderError as exc:
        failure = {
            "job_id": job_id,
            "diagram_id": diagram_id,
            "status": "failed",
            "error": str(exc),
        }
        if "metadata" in data:
            failure["metadata"] = data["metadata"]
        _publish(failure)
        raise
    except Exception as exc:  # pragma: no cover - defensive
        failure = {
            "job_id": job_id,
            "diagram_id": diagram_id,
            "status": "failed",
            "error": str(exc),
        }
        if "metadata" in data:
            failure["metadata"] = data["metadata"]
        _publish(failure)
        raise DiagramRenderError(f"unexpected rendering error: {exc}") from exc
