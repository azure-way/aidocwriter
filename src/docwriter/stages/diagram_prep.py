from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from ..config import get_settings
from ..messaging import publish_stage_event, send_queue_message
from ..storage import BlobStore


DIAGRAM_BLOCK_RE = re.compile(r"```(?P<lang>plantuml)\s+(?P<body>[\s\S]*?)```", re.IGNORECASE)
INLINE_UML_RE = re.compile(r"@startuml[\s\S]*?@enduml", re.IGNORECASE)
DIAGRAM_ID_RE = re.compile(r"(?:^|\n)\s*(?:'|//|#)\s*diagram_id\s*:\s*([A-Za-z0-9_.\-]+)", re.IGNORECASE)


def _sanitize_source(body: str) -> str:
    lines = body.splitlines()
    sanitized: List[str] = []
    started = False
    for line in lines:
        stripped = line.strip()
        if not started:
            if stripped.startswith("@startuml"):
                sanitized.append(stripped)
                started = True
            elif stripped.startswith(("'", "//", "#")):
                continue
            else:
                continue
        else:
            if stripped.startswith(("'", "//", "#")) and not stripped.lower().startswith("@enduml"):
                continue
            sanitized.append(stripped)
    if not started:
        # fallback: wrap body if @startuml missing
        sanitized = ["@startuml"] + [line.strip() for line in lines if line.strip()] + ["@enduml"]
    if not any(part.strip().startswith("@enduml") for part in sanitized):
        sanitized.append("@enduml")
    return "\n".join(sanitized)


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

    plan_specs = []
    try:
        plan_specs = (data.get("plan") or {}).get("diagram_specs") or []
    except Exception:
        plan_specs = []
    spec_lookup = {}
    ordered_specs: List[Dict[str, Any]] = []
    for spec in plan_specs:
        if not isinstance(spec, dict):
            continue
        ordered_specs.append(spec)
        spec_id = spec.get("diagram_id")
        if isinstance(spec_id, str) and spec_id:
            spec_lookup[spec_id] = spec

    def _claim_spec(spec_id: str | None, used: set[int]) -> Dict[str, Any] | None:
        if spec_id and spec_id in spec_lookup:
            spec = spec_lookup[spec_id]
            used.add(id(spec))
            return spec
        for candidate in ordered_specs:
            cid = id(candidate)
            if cid in used:
                continue
            used.add(cid)
            return candidate
        return None

    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9_.-]+", "-", value.lower())
        cleaned = cleaned.strip("-") or "diagram"
        return cleaned

    requests: List[Dict[str, Any]] = []
    preferred_format = _normalize_format(data.get("diagram_format"))
    used_specs: set[int] = set()
    for idx, (code_block, body) in enumerate(diagrams, start=1):
        ident_match = DIAGRAM_ID_RE.search(code_block)
        diagram_id = ident_match.group(1).strip() if ident_match else None
        spec = _claim_spec(diagram_id, used_specs)
        if not diagram_id:
            if spec and isinstance(spec.get("diagram_id"), str):
                diagram_id = spec.get("diagram_id")
        if not diagram_id:
            diagram_id = f"diagram_{idx}"
        safe_id = _slugify(diagram_id)
        fmt = _normalize_format((spec or {}).get("format") or preferred_format)
        alt_text = None
        if spec:
            alt_text = spec.get("alt_text") or spec.get("title") or spec.get("diagram_type")
        if not alt_text:
            alt_text = f"Diagram {diagram_id}"
        blob_path = f"jobs/{job_id}/images/{safe_id}.{fmt}"
        clean_source = _sanitize_source(body)
        requests.append(
            {
                "diagram_id": diagram_id,
                "source": clean_source,
                "code_block": code_block,
                "format": fmt,
                "blob_path": blob_path,
                "alt_text": alt_text,
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
