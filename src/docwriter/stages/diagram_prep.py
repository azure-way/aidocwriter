from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from ..config import get_settings
from ..messaging import publish_stage_event, send_queue_message
from ..storage import BlobStore, JobStoragePaths
from ..telemetry import track_exception


DIAGRAM_BLOCK_RE = re.compile(r"```(?P<lang>plantuml)\s+(?P<body>[\s\S]*?)```", re.IGNORECASE)
INLINE_UML_RE = re.compile(r"@startuml[\s\S]*?@enduml", re.IGNORECASE)
DIAGRAM_ID_RE = re.compile(r"(?:^|\n)\s*(?:'|//|#)\s*diagram_id\s*:\s*([A-Za-z0-9_.\-]+)", re.IGNORECASE)


def _sanitize_source(body: str) -> str:
    raw = body.replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.replace("\\n", "\n")
    lines = raw.split("\n")
    sanitized: List[str] = []
    started = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        if not started:
            if stripped.lower().startswith("@startuml"):
                sanitized.append(line)
                started = True
            elif stripped.startswith(("'", "//", "#")) and "diagram_id" in stripped.lower():
                continue
            elif stripped == "":
                continue
            else:
                sanitized.append(line)
        else:
            if stripped.startswith(("'", "//", "#")) and "diagram_id" in stripped.lower():
                continue
            sanitized.append(line)
    if not started:
        sanitized = ["@startuml"] + sanitized + ["@enduml"]
    text = "\n".join(sanitized)
    if "@enduml" not in text.lower():
        if not text.endswith("\n"):
            text += "\n"
        text += "@enduml"
    return text


def _validate_plantuml_source(source: str) -> List[str]:
    issues: List[str] = []
    lower = source.lower()
    if "@startuml" not in lower:
        issues.append("missing @startuml")
    if "@enduml" not in lower:
        issues.append("missing @enduml")
    if "```" in source:
        issues.append("contains markdown code fences inside PlantUML")
    if "@startmermaid" in lower or "```mermaid" in lower:
        issues.append("contains Mermaid instead of PlantUML")
    stripped = re.sub(r"@startuml", "", source, flags=re.IGNORECASE)
    stripped = re.sub(r"@enduml", "", stripped, flags=re.IGNORECASE).strip()
    if not stripped:
        issues.append("empty diagram body")
    return issues


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
    user_id = data.get("user_id")
    if not user_id:
        logging.warning("diagram prep payload missing user_id for job %s", job_id)
        return
    job_paths = JobStoragePaths(user_id=user_id, job_id=job_id)

    store = BlobStore()
    markdown = store.get_text(blob=data["out"])

    diagrams = _extract_diagrams(markdown)
    if not diagrams:
        payload = {**data, "diagram_results": []}
        send_queue_message(settings.sb_queue_finalize_ready, payload)
        publish_stage_event("DIAGRAM", "SKIPPED", payload, extra={"message": "No diagrams detected"})
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
    code_blocks: Dict[str, str] = {}
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
        blob_path = job_paths.images(f"{safe_id}.{fmt}")
        clean_source = _sanitize_source(body)
        validation_issues = _validate_plantuml_source(clean_source)
        if validation_issues:
            message = "; ".join(validation_issues)
            publish_stage_event(
                "DIAGRAM",
                "FAILED",
                {"job_id": job_id, "user_id": user_id},
                extra={"message": f"Invalid PlantUML for {diagram_id}: {message}"},
            )
            track_exception(
                RuntimeError("Invalid PlantUML"),
                {"job_id": job_id, "diagram_id": diagram_id, "issues": message, "stage": "DIAGRAM_PREP"},
            )
            return
        source_blob = job_paths.diagrams(f"{safe_id}.puml")
        try:
            store.put_text(blob=source_blob, text=clean_source)
        except Exception as exc:
            track_exception(exc, {"job_id": job_id, "stage": "DIAGRAM_PREP", "operation": "write_diagram_source"})
            continue
        code_blocks[diagram_id] = code_block
        requests.append(
            {
                "diagram_id": diagram_id,
                "source_path": source_blob,
                "format": fmt,
                "blob_path": blob_path,
                "alt_text": alt_text,
            }
        )

    finalize_payload = {**data, "diagram_code_blocks": code_blocks}
    finalize_payload.setdefault("user_id", user_id)
    message = {
        "job_id": job_id,
        "user_id": user_id,
        "diagram_requests": requests,
        "finalize_payload": finalize_payload,
    }
    send_queue_message(settings.sb_queue_diagram_render, message)
    diagram_total = len(requests)
    queue_message = (
        f"Queued {diagram_total} diagram{'s' if diagram_total != 1 else ''}"
        if diagram_total
        else "Queued diagram rendering"
    )
    publish_stage_event("DIAGRAM", "QUEUED", data, extra={"message": queue_message})


def _normalize_format(fmt: str | None) -> str:
    if not fmt:
        return "png"
    fmt = fmt.lower()
    return fmt if fmt in {"png", "svg"} else "png"
