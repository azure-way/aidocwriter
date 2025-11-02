from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from ..config import get_settings
from ..messaging import publish_stage_event, send_queue_message
from ..storage import BlobStore


DIAGRAM_BLOCK_RE = re.compile(r"```(?P<lang>plantuml)\s+(?P<body>[\s\S]*?)```", re.IGNORECASE)
INLINE_UML_RE = re.compile(r"@startuml[\s\S]*?@enduml", re.IGNORECASE)


def _extract_diagrams(markdown: str) -> List[Tuple[str, str]]:
    matches: List[Tuple[int, int, str, str]] = []

    for match in DIAGRAM_BLOCK_RE.finditer(markdown):
        body = match.group("body").strip()
        matches.append((*match.span(), match.group(0), body))

    def _span_overlaps(span: Tuple[int, int]) -> bool:
        return any(not (span[1] <= s or span[0] >= e) for s, e, _, _ in matches)

    for match in INLINE_UML_RE.finditer(markdown):
        span = match.span()
        if _span_overlaps(span):
            continue
        block = match.group(0)
        body = block.replace("@startuml", "", 1).rsplit("@enduml", 1)[0].strip()
        matches.append((*span, block, f"@startuml\n{body}\n@enduml"))

    matches.sort(key=lambda item: item[0])
    return [(block, body) for _, _, block, body in matches]


def process_diagram_prep(data: Dict[str, Any]) -> None:
    settings = get_settings()
    job_id = data.get("job_id")
    if not job_id:
        logging.warning("diagram prep payload missing job_id")
        return

    store = BlobStore()
    markdown = store.get_text(blob=data["out"])

    diagrams = _extract_diagrams(markdown)
    if not diagrams:
        payload = {**data, "diagram_results": []}
        send_queue_message(settings.sb_queue_finalize_ready, payload)
        publish_stage_event("DIAGRAM", "SKIPPED", payload)
        publish_stage_event("FINALIZE", "QUEUED", payload)
        return

    requests: List[Dict[str, Any]] = []
    preferred_format = _normalize_format(data.get("diagram_format"))
    for idx, (code_block, body) in enumerate(diagrams, start=1):
        diagram_id = f"diagram_{idx}"
        fmt = preferred_format
        blob_path = f"jobs/{job_id}/images/{diagram_id}.{fmt}"
        requests.append(
            {
                "diagram_id": diagram_id,
                "source": body,
                "code_block": code_block,
                "format": fmt,
                "blob_path": blob_path,
            }
        )

    message = {
        "job_id": job_id,
        "diagram_requests": requests,
        "finalize_payload": data,
    }
    send_queue_message(settings.sb_queue_diagram_render, message)
    publish_stage_event("DIAGRAM", "QUEUED", data)


def _normalize_format(fmt: str | None) -> str:
    if not fmt:
        return "png"
    fmt = fmt.lower()
    return fmt if fmt in {"png", "svg"} else "png"
