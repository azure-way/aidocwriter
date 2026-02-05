from __future__ import annotations

import json
import logging
import time
import re
from datetime import datetime
from typing import Any, Dict, Optional, Mapping, List

from docwriter.agents.cohesion_reviewer import CohesionReviewerAgent
from docwriter.agents.interviewer import InterviewerAgent
from docwriter.agents.planner import PlannerAgent
from docwriter.agents.reviewer import ReviewerAgent
from docwriter.agents.style_reviewer import StyleReviewerAgent
from docwriter.agents.summary_reviewer import SummaryReviewerAgent
from docwriter.agents.verifier import VerifierAgent
from docwriter.agents.writer import WriterAgent
from docwriter.artifacts import export_docx, export_pdf
from docwriter.config import get_settings, Settings
from docwriter.graph import build_dependency_graph
from docwriter.messaging import publish_stage_event, publish_status, send_queue_message
from docwriter.models import StatusEvent
from docwriter.stage_utils import (
    extract_sections,
    find_placeholder_sections,
    insert_table_of_contents,
    merge_revised_markdown,
    number_markdown_headings,
    parse_review_guidance,
    TITLE_PAGE_END,
)
from docwriter.storage import BlobStore, JobStoragePaths
from docwriter.summary import Summarizer
from docwriter.telemetry import stage_timer, track_event, track_exception, StageTiming
from .cycles import CycleState, enrich_details_with_cycles as _with_cycle_metadata
from docwriter.cycle_repository import ensure_cycle_state

import tiktoken

ENCODING_NAME = "cl100k_base"

logger = logging.getLogger(__name__)


def _job_paths(data: Mapping[str, Any]) -> JobStoragePaths:
    job_id = data.get("job_id")
    user_id = data.get("user_id")
    if not job_id:
        raise ValueError("job_id missing from stage payload")
    if not user_id:
        raise ValueError(f"user_id missing from stage payload for job {job_id}")
    return JobStoragePaths(user_id=user_id, job_id=job_id)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    try:
        encoding = tiktoken.get_encoding(ENCODING_NAME)
    except Exception:
        encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    try:
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 3)


def _init_review_progress(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Normalize review_progress into the new per-agent shape."""
    base = dict(raw) if isinstance(raw, Mapping) else {}

    def _agent_state(key: str) -> Dict[str, Any]:
        existing = base.get(key)
        state = dict(existing) if isinstance(existing, Mapping) else {}
        state.setdefault("sections_done", [])
        state.setdefault("done", False)
        if "accumulated" not in state:
            state["accumulated"] = {}
        return state

    normalized = {
        "tokens_total": base.get("tokens_total", 0) if isinstance(base.get("tokens_total"), (int, float)) else 0,
        "general": _agent_state("general"),
        "style": _agent_state("style"),
        "cohesion": _agent_state("cohesion"),
        "summary": _agent_state("summary"),
    }
    return normalized


def _ordered_section_ids(plan: Mapping[str, Any], sections: Mapping[str, str]) -> list[str]:
    outline = plan.get("outline", []) if isinstance(plan, Mapping) else []
    order: list[str] = []
    try:
        graph = build_dependency_graph(outline)
        order = [str(sid) for sid in graph.topological_order()]
    except Exception:
        order = [str(item.get("id")) for item in outline if isinstance(item, Mapping) and item.get("id") is not None]
    # Keep only sections present in the draft
    order = [sid for sid in order if sid in sections]
    if not order:
        order = list(sections.keys())
    return order


def _compose_section_batch(
    current_sid: str,
    sections: Mapping[str, str],
    id_to_section: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], str]:
    section = id_to_section.get(current_sid, {})
    deps = section.get("dependencies", []) or []
    dep_ids = [str(d) for d in deps if str(d) in sections]
    batch_ids: list[str] = []
    seen: set[str] = set()
    for sid in dep_ids + [current_sid]:
        if sid in sections and sid not in seen:
            batch_ids.append(sid)
            seen.add(sid)
    batch_text = "\n\n".join(sections[sid] for sid in batch_ids if sid in sections)
    return batch_ids, batch_text


def _dependency_stub(section_id: str, dependency_summaries: Mapping[str, str], id_to_section: Mapping[str, Mapping[str, Any]]) -> str:
    summary = (dependency_summaries.get(str(section_id)) or "").strip()
    title = (id_to_section.get(str(section_id)) or {}).get("title")
    title_part = f" ({title})" if title else ""
    if summary:
        return f"Dependency {section_id}{title_part} summary:\\n{summary}"
    return f"Dependency {section_id}{title_part} summary unavailable; refer to prior context."


def _build_batch_context(
    batch_ids: list[str],
    sections: Mapping[str, str],
    id_to_section: Mapping[str, Mapping[str, Any]],
    dependency_summaries: Mapping[str, str],
) -> tuple[str, list[str]]:
    """Compose a combined markdown for a batch plus dependency stubs.

    Returns the combined text and the ordered dependency ids included (excluding targets).
    """
    dep_ids: list[str] = []
    seen_deps: set[str] = set()
    for sid in batch_ids:
        section = id_to_section.get(str(sid), {})
        deps = section.get("dependencies", []) or []
        for dep in deps:
            dep_str = str(dep)
            if dep_str in batch_ids or dep_str in seen_deps:
                continue
            dep_ids.append(dep_str)
            seen_deps.add(dep_str)
    dependency_parts = [_dependency_stub(dep, dependency_summaries, id_to_section) for dep in dep_ids]
    batch_parts: list[str] = []
    if dependency_parts:
        batch_parts.append("\n\n".join(dependency_parts))
    for sid in batch_ids:
        section_text = sections.get(str(sid))
        if section_text:
            batch_parts.append(section_text)
    combined_text = "\n\n".join(batch_parts)
    return combined_text, dep_ids


def _plan_review_batches(
    ordered_section_ids: list[str],
    completed_ids: set[str],
    sections: Mapping[str, str],
    id_to_section: Mapping[str, Mapping[str, Any]],
    dependency_summaries: Mapping[str, str],
    settings: Settings,
) -> list[list[str]]:
    """Greedy batching: group sections that share dependencies while staying under limits."""
    max_batch = max(1, int(settings.review_batch_size or 1))
    max_tokens = max(1, int(settings.review_max_prompt_tokens or 1))
    remaining = [sid for sid in ordered_section_ids if sid not in completed_ids]
    batches: list[list[str]] = []
    current: list[str] = []

    for sid in remaining:
        candidate = current + [sid]
        candidate_text, _ = _build_batch_context(candidate, sections, id_to_section, dependency_summaries)
        candidate_tokens = _estimate_tokens(candidate_text)
        over_tokens = candidate_tokens > max_tokens
        over_size = len(candidate) > max_batch
        if current and (over_tokens or over_size):
            batches.append(current)
            current = [sid]
        else:
            current = candidate
        if len(current) >= max_batch:
            batches.append(current)
            current = []
    if current:
        batches.append(current)
    return batches


def _review_progress_path(job_paths: JobStoragePaths, cycle_idx: int) -> str:
    return job_paths.cycle(cycle_idx, "review_progress.json")


def _load_review_progress(job_paths: JobStoragePaths, cycle_idx: int) -> Dict[str, Any]:
    progress = _init_review_progress(None)
    try:
        store = BlobStore()
        text = store.get_text(blob=_review_progress_path(job_paths, cycle_idx))
        loaded = json.loads(text)
        progress = _init_review_progress(loaded)
    except Exception:
        pass
    return progress


def _persist_review_progress(job_paths: JobStoragePaths, cycle_idx: int, progress: Dict[str, Any]) -> None:
    try:
        store = BlobStore()
        store.put_text(blob=_review_progress_path(job_paths, cycle_idx), text=json.dumps(progress, ensure_ascii=False))
    except Exception as exc:
        track_exception(exc, {"job_id": job_paths.job_id, "stage": "REVIEW", "action": "persist_progress"})


def _strip_review_payload(data: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if k not in {"review_progress", "review_json", "style_json", "cohesion_json", "exec_summary_json"}}


def _apply_diagram_results(text: str, results: List[Dict[str, Any]], job_paths: JobStoragePaths) -> str:
    if not results:
        return text

    updated = text
    fallback_pattern = re.compile(r"```plantuml\s+([\s\S]*?)```", flags=re.IGNORECASE)
    inline_uml_pattern = re.compile(r"@startuml[\s\S]*?@enduml", flags=re.IGNORECASE)
    root_prefix = f"{job_paths.root}/"
    for item in results:
        code_block = item.get("code_block")
        blob_path = item.get("relative_path") or item.get("blob_path")
        if not code_block or not blob_path:
            continue
        relative_path = blob_path[len(root_prefix) :] if blob_path.startswith(root_prefix) else blob_path
        diagram_id = item.get("diagram_id")
        alt_text = item.get("alt_text") or (f"Diagram {diagram_id}" if diagram_id else "Diagram")
        replacement = f"![{alt_text}]({relative_path})"
        replaced = False
        if code_block in updated:
            updated = updated.replace(code_block, replacement, 1)
            replaced = True
        if not replaced and diagram_id:
            for match in fallback_pattern.finditer(updated):
                block = match.group(0)
                if f"diagram_id: {diagram_id}" in block or f"diagram_id:{diagram_id}" in block:
                    updated = updated.replace(block, replacement, 1)
                    replaced = True
                    break
        if not replaced and diagram_id:
            for match in inline_uml_pattern.finditer(updated):
                block = match.group(0)
                if f"diagram_id: {diagram_id}" in block or f"diagram_id:{diagram_id}" in block:
                    updated = updated.replace(block, replacement, 1)
                    replaced = True
                    break
        if not replaced:
            logging.warning(
                "Diagram block not found during finalize for job %s: %s",
                job_paths.job_id,
                diagram_id,
            )
    return updated


def _build_title_page(plan: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    title = (plan.get("title") if isinstance(plan, dict) else None) or metadata.get("title") or "Generated Document"
    audience = ""
    if isinstance(plan, dict):
        audience = str(plan.get("audience") or "").strip()
    if not audience:
        audience = str(metadata.get("audience") or "").strip()
    job_id = metadata.get("job_id")
    generated_on = datetime.utcnow().strftime("%Y-%m-%d")

    lines: List[str] = ["<!-- TITLE_PAGE_START -->", f"# {title}", ""]
    lines.append("")  # spacer
    footer: List[str] = []
    if audience:
        footer.append(f"**Audience:** {audience}")
    if job_id:
        footer.append(f"**Job ID:** {job_id}")
    footer.append(f"**Generated:** {generated_on}")
    if footer:
        lines.append("")
        lines.extend(footer)
    lines.extend(["", "<div style=\"page-break-after: always;\"></div>", "<!-- TITLE_PAGE_END -->", ""])
    return "\n".join(lines)


def _format_duration(duration_s: float | None) -> str:
    if duration_s is None:
        return "unknown duration"
    total_seconds = int(duration_s)
    minutes, seconds = divmod(total_seconds, 60)
    if minutes and seconds:
        return f"{minutes} min {seconds} sec"
    if minutes:
        return f"{minutes} min"
    return f"{seconds} sec"


def _pretty_stage(stage: str) -> str:
    return stage.replace("_", " ").title()


def _build_stage_message(
    stage_label: str,
    artifact: Optional[str],
    duration_s: Optional[float],
    tokens: Optional[int],
    model: Optional[str],
    notes: Optional[str] = None,
) -> str:
    parts = [
        f"stage completed: {stage_label}",
        f"stage document: {artifact or 'n/a'}",
        f"stage time: {_format_duration(duration_s)}",
        f"stage tokens: {f'{tokens:,}' if tokens is not None else 'n/a'}",
        f"stage model: {model or 'n/a'}",
    ]
    if notes:
        parts.append(notes)
    return " | ".join(parts)


def _usage_total(usage: Optional[Dict[str, Optional[int]]]) -> int:
    if not usage:
        return 0
    total = usage.get("total_tokens")
    if isinstance(total, int) and total >= 0:
        return total
    prompt = usage.get("prompt_tokens") or 0
    completion = usage.get("completion_tokens") or 0
    try:
        return int(prompt or 0) + int(completion or 0)
    except Exception:
        return 0


def _stage_completed_event(
    job_id: str,
    stage: str,
    timing: StageTiming,
    *,
    artifact: Optional[str] = None,
    tokens: Optional[int] = None,
    model: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[Mapping[str, Any]] = None,
) -> StatusEvent:
    stage_label = _pretty_stage(stage)
    message = _build_stage_message(stage_label, artifact, timing.duration_s, tokens, model, notes)
    details = {
        "duration_s": timing.duration_s,
        "tokens": tokens,
        "model": model,
        "artifact": artifact,
        "notes": notes,
    }
    details = {k: v for k, v in details.items() if v is not None}
    details = _with_cycle_metadata(details, source, cycle_idx=timing.cycle)
    extra = {"details": details} if details else {}
    user_id = source.get("user_id") if source else None
    if user_id:
        extra = extra or {}
        extra["user_id"] = user_id
    return StatusEvent(
        job_id=job_id,
        stage=f"{stage}_DONE",
        ts=time.time(),
        message=message,
        artifact=artifact,
        cycle=timing.cycle,
        extra=extra if extra else {},
    )


def process_plan_intake(data: Dict[str, Any], interviewer: InterviewerAgent | None = None) -> None:
    settings = get_settings()
    interviewer = interviewer or InterviewerAgent()
    ensure_cycle_state(data)
    job_paths = _job_paths(data)
    artifact_path = job_paths.intake("questions.json")
    with stage_timer(job_id=data["job_id"], stage="PLAN_INTAKE", user_id=job_paths.user_id) as timing:
        title = data["title"]
        questions = interviewer.propose_questions(title)
        try:
            store = BlobStore()
            store.put_text(
                blob=artifact_path, text=json.dumps(questions, indent=2)
            )
            context_snapshot = {
                "job_id": data.get("job_id"),
                "title": data.get("title"),
                "audience": data.get("audience"),
                "out": data.get("out"),
                "user_id": job_paths.user_id,
            }
            store.put_text(
                blob=job_paths.intake("context.json"),
                text=json.dumps(context_snapshot, indent=2),
            )
            sample_answers = {
                str(item.get("id")): item.get("sample", "") for item in questions if isinstance(item, dict)
            }
            store.put_text(
                blob=job_paths.intake("sample_answers.json"),
                text=json.dumps(sample_answers, indent=2),
            )
        except Exception as exc:
            track_exception(exc, {"job_id": data["job_id"], "stage": "PLAN_INTAKE"})
    question_tokens = _usage_total(getattr(interviewer.llm, "last_usage", None))
    if not question_tokens:
        question_tokens = _estimate_tokens(json.dumps(questions, ensure_ascii=False))
    intake_details = _with_cycle_metadata(
        {
            "duration_s": timing.duration_s,
            "tokens": question_tokens,
            "model": settings.planner_model,
            "artifact": artifact_path,
            "notes": "upload answers.json and resume",
        },
        data,
    )
    publish_status(
        StatusEvent(
            job_id=data["job_id"],
            stage="INTAKE_READY",
            ts=time.time(),
            message=_build_stage_message(
                "Plan Intake",
                artifact_path,
                timing.duration_s,
                question_tokens,
                settings.planner_model,
                "stage notes: upload answers.json and resume",
            ),
            artifact=artifact_path,
            extra={"details": intake_details, "user_id": job_paths.user_id},
        )
    )


def process_intake_resume(data: Dict[str, Any]) -> None:
    settings = get_settings()
    job_paths = _job_paths(data)
    job_id = job_paths.job_id
    if job_id:
        needed_keys = (
            "title",
            "audience",
            "out",
        )
        needs_context = any(data.get(key) in (None, "", []) for key in needed_keys)
        if needs_context:
            try:
                store = BlobStore()
                context_text = store.get_text(blob=job_paths.intake("context.json"))
                context = json.loads(context_text)
            except Exception as exc:
                context = None
                track_exception(exc, {"job_id": job_id, "stage": "INTAKE_RESUME", "operation": "load_intake_context"})
            if isinstance(context, dict):
                if not isinstance(data.get("title"), str) or not data.get("title"):
                    data["title"] = context.get("title")
                if not isinstance(data.get("audience"), str) or not data.get("audience"):
                    data["audience"] = context.get("audience")
                if not isinstance(data.get("out"), str) or not data.get("out"):
                    data["out"] = context.get("out")
        ensure_cycle_state(data)
    else:
        CycleState.from_context(data).apply(data)
    with stage_timer(job_id=data["job_id"], stage="INTAKE_RESUME", user_id=job_paths.user_id) as timing:
        publish_stage_event("PLAN", "QUEUED", data)
        send_queue_message(settings.sb_queue_plan, data)
        resume_details = _with_cycle_metadata(
            {
                "duration_s": timing.duration_s,
                "tokens": 0,
                "model": None,
                "artifact": None,
            },
            data,
        )
        publish_status(
            StatusEvent(
                job_id=data["job_id"],
                stage="INTAKE_RESUMED",
                ts=time.time(),
                message=_build_stage_message(
                    "Intake Resume",
                    None,
                    timing.duration_s,
                    0,
                    None,
                ),
                extra={"details": resume_details, "user_id": job_paths.user_id},
            )
        )


def process_plan(data: Dict[str, Any], planner: PlannerAgent | None = None) -> None:
    settings = get_settings()
    planner = planner or PlannerAgent()
    ensure_cycle_state(data)
    job_paths = _job_paths(data)
    store: BlobStore | None = None
    try:
        store = BlobStore()
    except Exception:
        store = None
    print(
        "[worker-plan] Processing job",
        data.get("job_id"),
        "title=",
        data.get("title"),
    )
    with stage_timer(job_id=data["job_id"], stage="PLAN", user_id=job_paths.user_id) as timing:
        audience = data.get("audience")
        title = data.get("title")
        length_pages = get_settings().default_length_pages

        answers: Dict[str, Any] = {}
        if store:
            try:
                plan_text = store.get_text(blob=job_paths.plan())
                existing_plan = json.loads(plan_text)
                title = existing_plan.get("title", title)
                audience = existing_plan.get("audience", audience)
                if existing_plan.get("length_pages") is not None:
                    length_pages = int(existing_plan.get("length_pages"))
            except Exception:
                pass

            try:
                answers_text = store.get_text(blob=job_paths.intake("answers.json"))
                answers = json.loads(answers_text)
                audience = answers.get("audience", audience)
                title = answers.get("title", title)
                length_pages = int(answers.get("length_pages", length_pages))
            except Exception:
                pass

        plan = planner.plan(title or "", audience=audience or "", length_pages=length_pages)
        try:
            plan.global_style.update({
                "tone": answers.get("tone") or plan.global_style.get("tone"),
                "pov": answers.get("pov") or plan.global_style.get("pov"),
                "structure": answers.get("structure") or plan.global_style.get("structure"),
                "constraints": answers.get("constraints") or plan.global_style.get("constraints"),
            })
        except Exception:
            pass
    payload = {
        **data,
        "plan": {
            "title": plan.title,
            "audience": plan.audience,
            "length_pages": max(60, plan.length_pages or get_settings().default_length_pages),
            "outline": plan.outline,
            "glossary": plan.glossary,
            "global_style": plan.global_style,
            "diagram_specs": plan.diagram_specs,
        },
        "dependency_summaries": {},
        "intake_answers": answers,
    }
    try:
        target_store = store or BlobStore()
        target_store.put_text(blob=job_paths.plan(), text=json.dumps(payload["plan"], indent=2))
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "PLAN"})
    publish_stage_event("WRITE", "QUEUED", payload)
    send_queue_message(settings.sb_queue_write, payload)
    artifact_path = job_paths.plan()
    plan_tokens = _usage_total(getattr(planner.llm, "last_usage", None))
    if not plan_tokens:
        plan_tokens = _estimate_tokens(json.dumps(payload["plan"], ensure_ascii=False))
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "PLAN",
            timing,
            artifact=artifact_path,
            tokens=plan_tokens,
            model=settings.planner_model,
            source=data,
        )
    )
    print("[worker-plan] Dispatched job", data.get("job_id"), "to writing queue")


def process_write(data: Dict[str, Any], writer: WriterAgent | None = None, summarizer: Summarizer | None = None) -> None:
    settings = get_settings()
    writer = writer or WriterAgent()
    summarizer = summarizer or Summarizer()
    ensure_cycle_state(data)
    job_paths = _job_paths(data)
    blob_path = data.get("out")
    if not isinstance(blob_path, str) or not blob_path:
        blob_path = BlobStore().allocate_document_blob(job_paths.job_id, job_paths.user_id)

    tokens_total = int(data.get("write_tokens_total") or 0)
    written_sections_raw = data.get("written_sections") or []
    written_sections = {str(s) for s in written_sections_raw if s is not None}
    with stage_timer(job_id=data["job_id"], stage="WRITE", user_id=job_paths.user_id) as timing:
        plan = data["plan"]
        outline = plan.get("outline", [])
        graph = build_dependency_graph(outline)
        order = graph.topological_order() if outline else []
        id_to_section = {str(s.get("id")): s for s in outline}
        dependency_summaries = data.get("dependency_summaries", {})
        renew_lock = data.get("_renew_lock")
        last_lock_renew = time.perf_counter()
        # pick up any existing draft body to keep building across batches
        existing_title_page = ""
        existing_body = ""
        try:
            store = BlobStore()
            existing_text = store.get_text(blob=blob_path)
            if TITLE_PAGE_END in existing_text:
                title_part, rest = existing_text.split(TITLE_PAGE_END, 1)
                existing_title_page = f"{title_part}{TITLE_PAGE_END}"
                existing_body = rest.strip()
            else:
                existing_body = existing_text.strip()
        except Exception:
            existing_title_page = ""
            existing_body = ""

        document_text_parts: list[str] = [existing_body] if existing_body else []
        remaining = [sid for sid in order if sid not in written_sections]
        batch_size = max(1, int(get_settings().write_batch_size or 5))
        batch = remaining[:batch_size]
        for idx, sid in enumerate(batch, start=1):
            section = id_to_section[sid]
            deps = section.get("dependencies", []) or []
            dep_context = "\n".join([dependency_summaries.get(str(d), "") for d in deps if dependency_summaries.get(str(d))])
            section_output = "".join(list(writer.write_section(plan=plan, section=section, dependency_context=dep_context)))
            document_text_parts.append(section_output)
            summary = summarizer.summarize_section("\n\n".join(document_text_parts))
            dependency_summaries[sid] = summary
            tokens_total += _usage_total(getattr(writer.llm, "last_usage", None))
            if renew_lock:
                try:
                    now = time.perf_counter()
                    if now - last_lock_renew > 60:  # renew at least once a minute
                        renew_lock()
                        last_lock_renew = now
                except Exception as exc:
                    track_exception(exc, {"job_id": data["job_id"], "stage": "WRITE", "action": "renew_lock"})
            written_sections.add(sid)
        body_text = "\n\n".join(document_text_parts)
        if existing_title_page:
            document_text = f"{existing_title_page}\n\n{body_text}".strip()
        else:
            title_page = _build_title_page(plan, data)
            document_text = f"{title_page}{body_text}" if body_text else title_page
    payload = {
        **data,
        "out": blob_path,
        "dependency_summaries": dependency_summaries,
        "written_sections": list(written_sections),
        "write_tokens_total": tokens_total,
    }
    try:
        store = BlobStore()
        store.put_text(blob=blob_path, text=document_text)
        store.put_text(blob=job_paths.draft(), text=document_text)
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "WRITE"})
    total_sections = len(order)
    completed_count = len(written_sections)
    if completed_count < total_sections:
        message = f"Section {completed_count} written of {total_sections}"
        publish_stage_event("WRITE", "QUEUED", payload, extra={"message": message})
        send_queue_message(settings.sb_queue_write, payload)
        progress_details = {"written": completed_count, "total": total_sections}
        status_payload = StatusEvent(
            job_id=data["job_id"],
            stage="WRITE_IN_PROGRESS",
            ts=time.time(),
            message=message,
            cycle=None,
            extra={"details": {**progress_details, "tokens": tokens_total}},
        ).to_payload()
        publish_status(status_payload)
    else:
        payload.pop("written_sections", None)
        tokens_total = tokens_total or _estimate_tokens(document_text)
        publish_stage_event("REVIEW", "QUEUED", payload)
        send_queue_message(settings.sb_queue_review_general, _strip_review_payload(payload))
        publish_status(
            _stage_completed_event(
                data["job_id"],
                "WRITE",
                timing,
                artifact=job_paths.draft(),
                tokens=tokens_total,
                model=settings.writer_model,
                source=data,
            )
        )


def _ensure_not_exhausted(cycle_state: CycleState, data: Mapping[str, Any], settings: Settings) -> bool:
    if cycle_state.completed >= cycle_state.requested:
        logger.info(
            "Job %s reached maximum cycles (%s); skipping additional review and moving to finalize queue",
            data.get("job_id"),
            cycle_state.requested,
        )
        publish_stage_event("DIAGRAM", "QUEUED", data)
        send_queue_message(settings.sb_queue_diagram_prep, data)
        return False
    return True


def process_review_general(data: Dict[str, Any], reviewer: ReviewerAgent | None = None) -> None:
    settings = get_settings()
    renew_lock = data.get("_renew_lock")
    reviewer = reviewer or ReviewerAgent()
    cycle_state = ensure_cycle_state(data)
    job_paths = _job_paths(data)
    if not _ensure_not_exhausted(cycle_state, data, settings):
        return
    cycle_idx = min(cycle_state.requested, cycle_state.completed + 1)
    progress = _load_review_progress(job_paths, cycle_idx)
    if progress["general"].get("done"):
        publish_stage_event("REVIEW", "QUEUED", data, extra={"message": "General review already complete; forwarding to style"})
        send_queue_message(settings.sb_queue_review_style, _strip_review_payload(data))
        return

    publish_stage_event("REVIEW", "START", data, extra={"message": "Running general reviewer"})
    with stage_timer(job_id=data["job_id"], stage="REVIEW", cycle=cycle_idx, user_id=job_paths.user_id) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        sections = extract_sections(draft)
        id_to_section = {str(s.get("id")): s for s in (data.get("plan", {}).get("outline", []) or [])}
        ordered_section_ids = _ordered_section_ids(data.get("plan", {}), sections)
        reviewed_sections = {str(s) for s in progress["general"].get("sections_done", [])}
        dependency_summaries = data.get("dependency_summaries", {}) or {}

        if not sections:
            review_json = reviewer.review(plan=data["plan"], draft_markdown=draft)
            data["review_json"] = review_json
            store.put_text(blob=job_paths.cycle(cycle_idx, "review.json"), text=review_json)
            progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(reviewer.llm, "last_usage", None))
            progress["general"]["done"] = True
        else:
            batches = _plan_review_batches(ordered_section_ids, reviewed_sections, sections, id_to_section, dependency_summaries, settings)
            if not batches:
                progress["general"]["done"] = True
            else:
                current_batch = batches[0]
                batch_text, dep_ids = _build_batch_context(current_batch, sections, id_to_section, dependency_summaries)
                logger.info(
                    "General review batch for job %s: targets=%s deps=%s est_tokens=%s",
                    data.get("job_id"),
                    current_batch,
                    dep_ids,
                    _estimate_tokens(batch_text),
                )
                section_meta = [
                    {"section_id": sid, "title": (id_to_section.get(sid) or {}).get("title")} for sid in current_batch
                ]
                review_json = reviewer.review_batch(plan=data["plan"], markdown=batch_text, sections=section_meta)
                try:
                    parsed = json.loads(review_json)
                except Exception:
                    parsed = {}
                accumulated = progress["general"].get("accumulated") or {
                    "findings": [],
                    "suggested_changes": [],
                    "revised_markdown": draft,
                }
                accumulated.setdefault("revised_markdown", draft)
                findings = accumulated.get("findings") or []
                suggestions = accumulated.get("suggested_changes") or []
                entries = parsed.get("sections") if isinstance(parsed, Mapping) else []
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, Mapping):
                            continue
                        findings.extend(entry.get("findings") or [])
                        suggestions.extend(entry.get("suggested_changes") or [])
                        revised_chunk = entry.get("revised_markdown")
                        if isinstance(revised_chunk, str) and revised_chunk.strip():
                            accumulated["revised_markdown"] = merge_revised_markdown(
                                accumulated.get("revised_markdown") or draft, revised_chunk
                            )
                        sid = entry.get("section_id")
                        if sid is not None:
                            reviewed_sections.add(str(sid))
                if not entries:
                    reviewed_sections.update(current_batch)
                accumulated["findings"] = findings
                accumulated["suggested_changes"] = suggestions
                progress["general"]["accumulated"] = accumulated
                progress["general"]["sections_done"] = sorted(reviewed_sections)
                progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(reviewer.llm, "last_usage", None))
                remaining_after_batch = [sid for sid in ordered_section_ids if sid not in reviewed_sections]
                if remaining_after_batch:
                    message = f"General review: {len(reviewed_sections)} of {len(ordered_section_ids)} sections (batch size {len(current_batch)})"
                    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
                    _persist_review_progress(job_paths, cycle_idx, progress)
                    send_queue_message(settings.sb_queue_review_general, _strip_review_payload(data))
                    status_payload = StatusEvent(
                        job_id=data["job_id"],
                        stage="REVIEW_IN_PROGRESS",
                        ts=time.time(),
                        message=message,
                        cycle=cycle_idx,
                        extra={
                            "details": {
                                "agent": "general",
                                "completed_sections": list(reviewed_sections),
                                "remaining_sections": remaining_after_batch,
                            }
                        },
                    ).to_payload()
                    publish_status(status_payload)
                    return
                final_review_json = json.dumps(progress[\"general\"].get(\"accumulated\", {}), ensure_ascii=False)
                store.put_text(blob=job_paths.cycle(cycle_idx, \"review.json\"), text=final_review_json)
                progress[\"general\"][\"done\"] = True

    try:
        if renew_lock:
            renew_lock()
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "REVIEW", "action": "renew_lock"})

    _persist_review_progress(job_paths, cycle_idx, progress)
    message = "General review complete; queuing style reviewer"
    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
    send_queue_message(settings.sb_queue_review_style, _strip_review_payload(data))
    status_payload = StatusEvent(
        job_id=data["job_id"],
        stage="REVIEW_IN_PROGRESS",
        ts=time.time(),
        message=message,
        cycle=cycle_idx,
        extra={"details": {"agent": "general", "completed_sections": progress["general"].get("sections_done", [])}},
    ).to_payload()
    publish_status(status_payload)


def _accumulate_section_guidance(
    progress: Dict[str, Any],
    agent_key: str,
    section_id: str,
    section_title: str | None,
    issues: list[Any],
    suggestions: list[Any],
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    agent_state = progress[agent_key]
    accumulated = agent_state.get("accumulated") or {"issues": [], "suggestions": [], "sections": []}
    accumulated["issues"] = (accumulated.get("issues") or []) + (issues or [])
    accumulated["suggestions"] = (accumulated.get("suggestions") or []) + (suggestions or [])
    section_entry: Dict[str, Any] = {
        "section_id": section_id,
        "title": section_title,
        "issues": issues or [],
        "suggestions": suggestions or [],
    }
    if extra_fields:
        section_entry.update(extra_fields)
    sections_list = accumulated.get("sections") or []
    sections_list.append(section_entry)
    accumulated["sections"] = sections_list
    agent_state["accumulated"] = accumulated
    sections_done = set(agent_state.get("sections_done") or [])
    sections_done.add(section_id)
    agent_state["sections_done"] = sorted(sections_done)
    return progress


def process_review_style(data: Dict[str, Any], style_agent: StyleReviewerAgent | None = None) -> None:
    settings = get_settings()
    style_agent = style_agent or StyleReviewerAgent()
    cycle_state = ensure_cycle_state(data)
    job_paths = _job_paths(data)
    if not _ensure_not_exhausted(cycle_state, data, settings):
        return
    cycle_idx = min(cycle_state.requested, cycle_state.completed + 1)
    progress = _load_review_progress(job_paths, cycle_idx)
    if progress["style"].get("done"):
        publish_stage_event("REVIEW", "QUEUED", data, extra={"message": "Style review already complete; forwarding to cohesion"})
        send_queue_message(settings.sb_queue_review_cohesion, _strip_review_payload(data))
        return

    publish_stage_event("REVIEW", "START", data, extra={"message": "Running style reviewer"})
    with stage_timer(job_id=data["job_id"], stage="REVIEW", cycle=cycle_idx, user_id=job_paths.user_id) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        sections = extract_sections(draft)
        id_to_section = {str(s.get("id")): s for s in (data.get("plan", {}).get("outline", []) or [])}
        ordered_section_ids = _ordered_section_ids(data.get("plan", {}), sections)
        reviewed_sections = {str(s) for s in progress["style"].get("sections_done", [])}
        dependency_summaries = data.get("dependency_summaries", {}) or {}

        if not sections:
            style_json = style_agent.review_style(plan=data["plan"], markdown=draft)
            data["style_json"] = style_json
            store.put_text(blob=job_paths.cycle(cycle_idx, "style.json"), text=style_json)
            progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(style_agent.llm, "last_usage", None))
            progress["style"]["done"] = True
        else:
            batches = _plan_review_batches(ordered_section_ids, reviewed_sections, sections, id_to_section, dependency_summaries, settings)
            if not batches:
                progress["style"]["done"] = True
            else:
                current_batch = batches[0]
                batch_text, dep_ids = _build_batch_context(current_batch, sections, id_to_section, dependency_summaries)
                logger.info(
                    "Style review batch for job %s: targets=%s deps=%s est_tokens=%s",
                    data.get("job_id"),
                    current_batch,
                    dep_ids,
                    _estimate_tokens(batch_text),
                )
                section_meta = [
                    {"section_id": sid, "title": (id_to_section.get(sid) or {}).get("title")} for sid in current_batch
                ]
                style_json = style_agent.review_style_batch(plan=data["plan"], markdown=batch_text, sections=section_meta)
                try:
                    parsed = json.loads(style_json)
                except Exception:
                    parsed = {}
                entries = parsed.get("sections") if isinstance(parsed, Mapping) else []
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, Mapping):
                            continue
                        issues = entry.get("issues") if isinstance(entry.get("issues"), list) else []
                        suggestions = entry.get("suggestions") if isinstance(entry.get("suggestions"), list) else []
                        revised_snippets = entry.get("revised_snippets")
                        sid = str(entry.get("section_id")) if entry.get("section_id") is not None else None
                        if sid:
                            progress = _accumulate_section_guidance(
                                progress,
                                "style",
                                sid,
                                id_to_section.get(sid, {}).get("title"),
                                issues,
                                suggestions,
                                {"revised_snippets": revised_snippets} if revised_snippets else {},
                            )
                if not entries:
                    for sid in current_batch:
                        progress = _accumulate_section_guidance(
                            progress, "style", sid, id_to_section.get(sid, {}).get("title"), [], []
                        )
                progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(style_agent.llm, "last_usage", None))
                remaining_after_batch = [sid for sid in ordered_section_ids if sid not in set(progress["style"].get("sections_done", []))]
                if remaining_after_batch:
                    message = f"Style review: {len(progress['style']['sections_done'])} of {len(ordered_section_ids)} sections (batch size {len(current_batch)})"
                    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
                    _persist_review_progress(job_paths, cycle_idx, progress)
                    send_queue_message(settings.sb_queue_review_style, _strip_review_payload(data))
                    status_payload = StatusEvent(
                        job_id=data["job_id"],
                        stage="REVIEW_IN_PROGRESS",
                        ts=time.time(),
                        message=message,
                        cycle=cycle_idx,
                        extra={
                            "details": {
                                "agent": "style",
                                "completed_sections": progress["style"]["sections_done"],
                                "remaining_sections": remaining_after_batch,
                            }
                        },
                    ).to_payload()
                    publish_status(status_payload)
                    return
            final_style_json = json.dumps(progress["style"]["accumulated"], ensure_ascii=False)
            store.put_text(blob=job_paths.cycle(cycle_idx, "style.json"), text=final_style_json)
            progress["style"]["done"] = True

    _persist_review_progress(job_paths, cycle_idx, progress)
    message = "Style review complete; queuing cohesion reviewer"
    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
    send_queue_message(settings.sb_queue_review_cohesion, _strip_review_payload(data))
    status_payload = StatusEvent(
        job_id=data["job_id"],
        stage="REVIEW_IN_PROGRESS",
        ts=time.time(),
        message=message,
        cycle=cycle_idx,
        extra={"details": {"agent": "style", "completed_sections": progress["style"].get("sections_done", [])}},
    ).to_payload()
    publish_status(status_payload)


def process_review_cohesion(data: Dict[str, Any], cohesion_agent: CohesionReviewerAgent | None = None) -> None:
    settings = get_settings()
    cohesion_agent = cohesion_agent or CohesionReviewerAgent()
    cycle_state = ensure_cycle_state(data)
    job_paths = _job_paths(data)
    if not _ensure_not_exhausted(cycle_state, data, settings):
        return
    cycle_idx = min(cycle_state.requested, cycle_state.completed + 1)
    progress = _load_review_progress(job_paths, cycle_idx)
    if progress["cohesion"].get("done"):
        publish_stage_event("REVIEW", "QUEUED", data, extra={"message": "Cohesion review already complete; forwarding to summary"})
        send_queue_message(settings.sb_queue_review_summary, _strip_review_payload(data))
        return

    publish_stage_event("REVIEW", "START", data, extra={"message": "Running cohesion reviewer"})
    with stage_timer(job_id=data["job_id"], stage="REVIEW", cycle=cycle_idx, user_id=job_paths.user_id) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        sections = extract_sections(draft)
        id_to_section = {str(s.get("id")): s for s in (data.get("plan", {}).get("outline", []) or [])}
        ordered_section_ids = _ordered_section_ids(data.get("plan", {}), sections)
        reviewed_sections = {str(s) for s in progress["cohesion"].get("sections_done", [])}
        dependency_summaries = data.get("dependency_summaries", {}) or {}

        if not sections:
            cohesion_json = cohesion_agent.review_cohesion(plan=data["plan"], markdown=draft)
            data["cohesion_json"] = cohesion_json
            store.put_text(blob=job_paths.cycle(cycle_idx, "cohesion.json"), text=cohesion_json)
            progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(cohesion_agent.llm, "last_usage", None))
            progress["cohesion"]["done"] = True
        else:
            batches = _plan_review_batches(ordered_section_ids, reviewed_sections, sections, id_to_section, dependency_summaries, settings)
            if not batches:
                progress["cohesion"]["done"] = True
            else:
                current_batch = batches[0]
                batch_text, dep_ids = _build_batch_context(current_batch, sections, id_to_section, dependency_summaries)
                logger.info(
                    "Cohesion review batch for job %s: targets=%s deps=%s est_tokens=%s",
                    data.get("job_id"),
                    current_batch,
                    dep_ids,
                    _estimate_tokens(batch_text),
                )
                section_meta = [
                    {"section_id": sid, "title": (id_to_section.get(sid) or {}).get("title")} for sid in current_batch
                ]
                cohesion_json = cohesion_agent.review_cohesion_batch(plan=data["plan"], markdown=batch_text, sections=section_meta)
                try:
                    parsed = json.loads(cohesion_json)
                except Exception:
                    parsed = {}
                entries = parsed.get("sections") if isinstance(parsed, Mapping) else []
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, Mapping):
                            continue
                        issues = entry.get("issues") if isinstance(entry.get("issues"), list) else []
                        suggestions = entry.get("suggestions") if isinstance(entry.get("suggestions"), list) else []
                        sid = str(entry.get("section_id")) if entry.get("section_id") is not None else None
                        if sid:
                            progress = _accumulate_section_guidance(
                                progress,
                                "cohesion",
                                sid,
                                id_to_section.get(sid, {}).get("title"),
                                issues,
                                suggestions,
                            )
                if not entries:
                    for sid in current_batch:
                        progress = _accumulate_section_guidance(
                            progress, "cohesion", sid, id_to_section.get(sid, {}).get("title"), [], []
                        )
                progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(cohesion_agent.llm, "last_usage", None))
                remaining_after_batch = [sid for sid in ordered_section_ids if sid not in set(progress["cohesion"].get("sections_done", []))]
                if remaining_after_batch:
                    message = f"Cohesion review: {len(progress['cohesion']['sections_done'])} of {len(ordered_section_ids)} sections (batch size {len(current_batch)})"
                    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
                    _persist_review_progress(job_paths, cycle_idx, progress)
                    send_queue_message(settings.sb_queue_review_cohesion, _strip_review_payload(data))
                    status_payload = StatusEvent(
                        job_id=data["job_id"],
                        stage="REVIEW_IN_PROGRESS",
                        ts=time.time(),
                        message=message,
                        cycle=cycle_idx,
                        extra={
                            "details": {
                                "agent": "cohesion",
                                "completed_sections": progress["cohesion"]["sections_done"],
                                "remaining_sections": remaining_after_batch,
                            }
                        },
                    ).to_payload()
                    publish_status(status_payload)
                    return
            final_cohesion_json = json.dumps(progress["cohesion"]["accumulated"], ensure_ascii=False)
            store.put_text(blob=job_paths.cycle(cycle_idx, "cohesion.json"), text=final_cohesion_json)
            progress["cohesion"]["done"] = True

    _persist_review_progress(job_paths, cycle_idx, progress)
    message = "Cohesion review complete; queuing summary reviewer"
    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
    send_queue_message(settings.sb_queue_review_summary, _strip_review_payload(data))
    status_payload = StatusEvent(
        job_id=data["job_id"],
        stage="REVIEW_IN_PROGRESS",
        ts=time.time(),
        message=message,
        cycle=cycle_idx,
        extra={"details": {"agent": "cohesion", "completed_sections": progress["cohesion"].get("sections_done", [])}},
    ).to_payload()
    publish_status(status_payload)


def process_review_summary(data: Dict[str, Any], summary_agent: SummaryReviewerAgent | None = None) -> None:
    settings = get_settings()
    summary_agent = summary_agent or SummaryReviewerAgent()
    cycle_state = ensure_cycle_state(data)
    job_paths = _job_paths(data)
    if not _ensure_not_exhausted(cycle_state, data, settings):
        return
    cycle_idx = min(cycle_state.requested, cycle_state.completed + 1)
    progress = _load_review_progress(job_paths, cycle_idx)
    if progress["summary"].get("done"):
        publish_stage_event("VERIFY", "QUEUED", data, extra={"message": "Summary review already complete; forwarding to verify"})
        review_tokens = int(progress.get("tokens_total") or 0)
        publish_status(
            _stage_completed_event(
                data["job_id"],
                "REVIEW",
                StageTiming(job_id=data["job_id"], stage="REVIEW", cycle=cycle_idx, start=time.perf_counter(), duration_s=0.0),
                artifact=job_paths.cycle(cycle_idx, "review.json"),
                tokens=review_tokens,
                model=settings.reviewer_model,
                source=data,
            )
        )
        send_queue_message(settings.sb_queue_verify, _strip_review_payload(data))
        return

    publish_stage_event("REVIEW", "START", data, extra={"message": "Running executive summary reviewer"})
    with stage_timer(job_id=data["job_id"], stage="REVIEW", cycle=cycle_idx, user_id=job_paths.user_id) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        sections = extract_sections(draft)
        id_to_section = {str(s.get("id")): s for s in (data.get("plan", {}).get("outline", []) or [])}
        ordered_section_ids = _ordered_section_ids(data.get("plan", {}), sections)
        reviewed_sections = {str(s) for s in progress["summary"].get("sections_done", [])}
        dependency_summaries = data.get("dependency_summaries", {}) or {}

        if not sections:
            summary_json = summary_agent.review_executive_summary(plan=data["plan"], markdown=draft)
            data["exec_summary_json"] = summary_json
            store.put_text(blob=job_paths.cycle(cycle_idx, "executive_summary.json"), text=summary_json)
            progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(summary_agent.llm, "last_usage", None))
            progress["summary"]["done"] = True
        else:
            batches = _plan_review_batches(ordered_section_ids, reviewed_sections, sections, id_to_section, dependency_summaries, settings)
            if not batches:
                progress["summary"]["done"] = True
            else:
                current_batch = batches[0]
                batch_text, dep_ids = _build_batch_context(current_batch, sections, id_to_section, dependency_summaries)
                logger.info(
                    "Summary review batch for job %s: targets=%s deps=%s est_tokens=%s",
                    data.get("job_id"),
                    current_batch,
                    dep_ids,
                    _estimate_tokens(batch_text),
                )
                section_meta = [
                    {"section_id": sid, "title": (id_to_section.get(sid) or {}).get("title")} for sid in current_batch
                ]
                summary_json = summary_agent.review_executive_summary_batch(
                    plan=data["plan"], markdown=batch_text, sections=section_meta
                )
                try:
                    parsed = json.loads(summary_json)
                except Exception:
                    parsed = {}
                entries = parsed.get("sections") if isinstance(parsed, Mapping) else []
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, Mapping):
                            continue
                        issues = entry.get("issues") if isinstance(entry.get("issues"), list) else []
                        suggestions = entry.get("suggestions") if isinstance(entry.get("suggestions"), list) else []
                        section_summary = entry.get("summary") if isinstance(entry.get("summary"), str) else None
                        sid = str(entry.get("section_id")) if entry.get("section_id") is not None else None
                        if sid:
                            progress = _accumulate_section_guidance(
                                progress,
                                "summary",
                                sid,
                                id_to_section.get(sid, {}).get("title"),
                                issues,
                                suggestions,
                                {"summary": section_summary} if section_summary else {},
                            )
                if not entries:
                    for sid in current_batch:
                        progress = _accumulate_section_guidance(
                            progress, "summary", sid, id_to_section.get(sid, {}).get("title"), [], []
                        )
                progress["tokens_total"] = progress.get("tokens_total", 0) + _usage_total(getattr(summary_agent.llm, "last_usage", None))
                remaining_after_batch = [sid for sid in ordered_section_ids if sid not in set(progress["summary"].get("sections_done", []))]
                if remaining_after_batch:
                    message = f"Summary review: {len(progress['summary']['sections_done'])} of {len(ordered_section_ids)} sections (batch size {len(current_batch)})"
                    publish_stage_event("REVIEW", "QUEUED", data, extra={"message": message})
                    _persist_review_progress(job_paths, cycle_idx, progress)
                    send_queue_message(settings.sb_queue_review_summary, _strip_review_payload(data))
                    status_payload = StatusEvent(
                        job_id=data["job_id"],
                        stage="REVIEW_IN_PROGRESS",
                        ts=time.time(),
                        message=message,
                        cycle=cycle_idx,
                        extra={
                            "details": {
                                "agent": "summary",
                                "completed_sections": progress["summary"]["sections_done"],
                                "remaining_sections": remaining_after_batch,
                            }
                        },
                    ).to_payload()
                    publish_status(status_payload)
                    return
            sections_entries = progress["summary"]["accumulated"].get("sections", []) if isinstance(progress["summary"].get("accumulated"), dict) else []
            combined_summary_parts: list[str] = []
            for entry in sections_entries:
                if not isinstance(entry, Mapping):
                    continue
                title = entry.get("title") or entry.get("section_id")
                summary_text = entry.get("summary")
                if summary_text:
                    combined_summary_parts.append(f"{title}: {summary_text}")
            combined_summary = "\n\n".join(combined_summary_parts).strip() if combined_summary_parts else parsed.get("summary", "")
            final_summary_json = json.dumps(
                {
                    **(progress["summary"].get("accumulated") or {}),
                    "summary": combined_summary or (parsed.get("summary") if isinstance(parsed, dict) else ""),
                },
                ensure_ascii=False,
            )
            store.put_text(blob=job_paths.cycle(cycle_idx, "executive_summary.json"), text=final_summary_json)
            progress["summary"]["done"] = True

    _persist_review_progress(job_paths, cycle_idx, progress)
    review_tokens = int(progress.get("tokens_total") or 0)
    publish_stage_event("VERIFY", "QUEUED", data, extra={"message": "Summary review complete; queuing verify"})
    send_queue_message(settings.sb_queue_verify, _strip_review_payload(data))
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "REVIEW",
            timing,
            artifact=job_paths.cycle(cycle_idx, "review.json"),
            tokens=review_tokens,
            model=settings.reviewer_model,
            source=data,
        )
    )


# Backward-compatible entrypoint for legacy single-queue review
def process_review(data: Dict[str, Any], reviewer: ReviewerAgent | None = None) -> None:
    process_review_general(data, reviewer)


def process_verify(data: Dict[str, Any], verifier: VerifierAgent | None = None) -> None:
    settings = get_settings()
    verifier = verifier or VerifierAgent()
    cycle_state = ensure_cycle_state(data)
    cycle_idx = min(cycle_state.requested, cycle_state.completed + 1)
    job_paths = _job_paths(data)
    publish_stage_event("VERIFY", "START", data)
    with stage_timer(job_id=data["job_id"], stage="VERIFY", cycle=cycle_idx, user_id=job_paths.user_id) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        try:
            review_text = store.get_text(blob=job_paths.cycle(cycle_idx, "review.json"))
        except Exception:
            review_text = data.get("review_json", "{}")
        try:
            review_data = json.loads(review_text or "{}")
            revised = review_data.get("revised_markdown")
            if isinstance(revised, str) and revised.strip():
                merged = merge_revised_markdown(draft, revised)
                if merged != draft:
                    draft = merged
                    try:
                        store.put_text(blob=data["out"], text=merged)
                        store.put_text(blob=job_paths.cycle(cycle_idx, "revision.md"), text=merged)
                    except Exception:
                        pass
        except Exception:
            pass
        placeholder_sections = find_placeholder_sections(draft)
        try:
            verification_json = verifier.verify(
                dependency_summaries=data.get("dependency_summaries", {}), final_markdown=draft
            )
        except Exception as exc:
            track_exception(exc, {"job_id": data["job_id"], "stage": "VERIFY"})
            raise
    payload = {**data, "verification_json": verification_json}
    cycle_state = ensure_cycle_state(payload)
    try:
        store = BlobStore()
        store.put_text(blob=job_paths.cycle(cycle_idx, "contradictions.json"), text=verification_json)
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "VERIFY"})
    try:
        verification = json.loads(verification_json)
        contradictions = verification.get("contradictions", [])
    except Exception:
        contradictions = []

    try:
        style_raw = BlobStore().get_text(blob=job_paths.cycle(cycle_idx, "style.json"))
    except Exception:
        style_raw = data.get("style_json")
    try:
        cohesion_raw = BlobStore().get_text(blob=job_paths.cycle(cycle_idx, "cohesion.json"))
    except Exception:
        cohesion_raw = data.get("cohesion_json")

    style_guidance, style_sections = parse_review_guidance(style_raw)
    cohesion_guidance, cohesion_sections = parse_review_guidance(cohesion_raw)
    needs_rewrite = (
        bool(contradictions)
        or bool(style_guidance)
        or bool(cohesion_guidance)
        or bool(placeholder_sections)
    )

    payload["placeholder_sections"] = sorted(placeholder_sections)
    payload["requires_rewrite"] = needs_rewrite
    artifact_path = job_paths.cycle(cycle_idx, "contradictions.json")
    verify_tokens = _usage_total(getattr(verifier.llm, "last_usage", None))
    if not verify_tokens:
        verify_tokens = _estimate_tokens(verification_json)
    notes_list: list[str] = []
    if contradictions:
        notes_list.append("stage notes: contradictions detected")
    if style_guidance:
        notes_list.append("stage notes: style revisions pending")
    if cohesion_guidance:
        notes_list.append("stage notes: cohesion guidance pending")
    if placeholder_sections:
        notes_list.append("stage notes: placeholders present")
    notes_message = "; ".join(notes_list) if notes_list else None
    publish_status(
        StatusEvent(
            job_id=data["job_id"],
            stage="VERIFY_DONE",
            ts=time.time(),
            message=_build_stage_message(
                "Verify",
                artifact_path,
                timing.duration_s,
                verify_tokens,
                settings.reviewer_model,
                notes_message,
            ),
            cycle=cycle_idx,
            has_contradictions=bool(contradictions),
            style_issues=bool(style_guidance),
            cohesion_issues=bool(cohesion_guidance),
            placeholder_sections=bool(placeholder_sections),
            artifact=artifact_path,
            extra={
                "details": _with_cycle_metadata(
                    {
                        "duration_s": timing.duration_s,
                        "tokens": verify_tokens,
                        "model": settings.reviewer_model,
                        "artifact": artifact_path,
                        **({"notes": notes_message} if notes_message else {}),
                    },
                    payload,
                    cycle_idx=cycle_idx,
                ),
                "user_id": job_paths.user_id,
            },
        )
    )

    publish_stage_event("REWRITE", "QUEUED", payload)
    send_queue_message(settings.sb_queue_rewrite, payload)


def process_rewrite(data: Dict[str, Any], writer: WriterAgent | None = None) -> None:
    settings = get_settings()
    writer = writer or WriterAgent()
    cycle_state = ensure_cycle_state(data)
    job_paths = _job_paths(data)
    rewrite_tokens_total = 0
    requires_rewrite = bool(data.get("requires_rewrite"))
    rewritten_sections = {str(s) for s in (data.get("rewritten_sections") or []) if s is not None}
    cycle_idx = min(cycle_state.requested, cycle_state.completed + 1)
    publish_stage_event("REWRITE", "START", data)
    with stage_timer(job_id=data["job_id"], stage="REWRITE", cycle=cycle_idx, user_id=job_paths.user_id) as timing:
        plan = data["plan"]
        store = BlobStore()
        text = store.get_text(blob=data["out"])
        if requires_rewrite:
            try:
                verification_text = BlobStore().get_text(blob=job_paths.cycle(cycle_idx, "contradictions.json"))
            except Exception:
                verification_text = data.get("verification_json", "{}")
            try:
                verification = json.loads(verification_text or "{}")
            except Exception:
                verification = {"contradictions": []}
            contradictions = verification.get("contradictions", [])
            id_to_section = {str(s.get("id")): s for s in plan.get("outline", [])}
            dependency_summaries = data.get("dependency_summaries", {})

            try:
                style_raw = BlobStore().get_text(blob=job_paths.cycle(cycle_idx, "style.json"))
            except Exception:
                style_raw = data.get("style_json")
            try:
                cohesion_raw = BlobStore().get_text(blob=job_paths.cycle(cycle_idx, "cohesion.json"))
            except Exception:
                cohesion_raw = data.get("cohesion_json")

            style_guidance, style_sections = parse_review_guidance(style_raw)
            cohesion_guidance, cohesion_sections = parse_review_guidance(cohesion_raw)
            combined_guidance = "\n".join(filter(None, [style_guidance, cohesion_guidance]))

            affected = {str(c.get("section_id")) for c in contradictions if c.get("section_id")}
            affected.update(style_sections)
            affected.update(cohesion_sections)

            if not affected and combined_guidance:
                affected = set(id_to_section.keys())

            placeholder_sections = {str(s) for s in data.get("placeholder_sections", [])}
            affected.update(placeholder_sections)

            remaining = [sid for sid in affected if sid not in rewritten_sections]
            batch_size = max(1, int(settings.write_batch_size or 5))
            batch = remaining[:batch_size]

            if batch:
                for sid in batch:
                    section = id_to_section.get(sid)
                    if not section:
                        continue
                    deps = section.get("dependencies", []) or []
                    dep_context = "\n".join(
                        [dependency_summaries.get(str(d), "") for d in deps if dependency_summaries.get(str(d))]
                    )
                    try:
                        new_text = "".join(
                            list(
                                writer.write_section(
                                    plan=plan,
                                    section=section,
                                    dependency_context=dep_context,
                                    extra_guidance=combined_guidance,
                                )
                            )
                        )
                    except Exception as exc:
                        track_exception(exc, {"job_id": job_paths.job_id, "stage": "REWRITE", "section": sid})
                        raise
                    start_marker = f"<!-- SECTION:{sid}:START -->"
                    end_marker = f"<!-- SECTION:{sid}:END -->"
                    start_idx = text.find(start_marker)
                    end_idx = text.find(end_marker)
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        end_idx += len(end_marker)
                        text = text[:start_idx] + new_text + text[end_idx:]
                    rewrite_tokens_total += _usage_total(getattr(writer.llm, "last_usage", None))
                    rewritten_sections.add(sid)
                store.put_text(blob=data["out"], text=text)
                try:
                    store.put_text(blob=job_paths.cycle(cycle_idx, "rewrite.md"), text=text)
                except Exception:
                    pass
            remaining_after_batch = [sid for sid in affected if sid not in rewritten_sections]
            if remaining_after_batch:
                progress_msg = f"Rewrite sections: {len(rewritten_sections)} done of {len(affected)}"
                progress_payload = {
                    **data,
                    "out": data["out"],
                    "requires_rewrite": True,
                    "rewritten_sections": list(rewritten_sections),
                    "dependency_summaries": data.get("dependency_summaries", {}),
                    "placeholder_sections": list(placeholder_sections),
                }
                publish_stage_event("REWRITE", "QUEUED", progress_payload, extra={"message": progress_msg})
                send_queue_message(settings.sb_queue_rewrite, progress_payload)
                status_payload = StatusEvent(
                    job_id=data["job_id"],
                    stage="REWRITE_IN_PROGRESS",
                    ts=time.time(),
                    message=progress_msg,
                    cycle=cycle_idx,
                    extra={"details": {"written": len(rewritten_sections), "total": len(affected)}},
                ).to_payload()
                publish_status(status_payload)
                return
    payload = {
        **data,
        "placeholder_sections": [],
        "rewritten_sections": list(rewritten_sections),
    }
    payload.pop("review_progress", None)
    next_completed = min(cycle_state.requested, cycle_state.completed + 1)
    next_cycle_state = CycleState(cycle_state.requested, next_completed)
    next_cycle_state.apply(payload)
    payload["requires_rewrite"] = False
    if next_cycle_state.completed < next_cycle_state.requested:
        publish_stage_event("REVIEW", "QUEUED", payload)
        send_queue_message(settings.sb_queue_review_general, payload)
    else:
        publish_stage_event("DIAGRAM", "QUEUED", payload)
        send_queue_message(settings.sb_queue_diagram_prep, payload)
    if not rewrite_tokens_total:
        rewrite_tokens_total = _estimate_tokens(text)
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "REWRITE",
            timing,
            artifact=data.get("out"),
            tokens=rewrite_tokens_total,
            model=settings.writer_model,
            source=payload,
        )
    )


def process_finalize(data: Dict[str, Any]) -> None:
    ensure_cycle_state(data)
    final_text = ""
    job_paths = _job_paths(data)
    with stage_timer(job_id=data["job_id"], stage="FINALIZE", user_id=job_paths.user_id) as timing:
        try:
            store = BlobStore()
            target_blob = data["out"]
            final_text = store.get_text(blob=target_blob)
            final_text = _apply_diagram_results(
                final_text,
                data.get("diagram_results", []),
                job_paths,
            )
            final_text = number_markdown_headings(final_text)
            final_text = insert_table_of_contents(final_text)
            store.put_text(blob=job_paths.final("md"), text=final_text)
            pdf_bytes = export_pdf(final_text, {}, store, job_paths)
            if pdf_bytes:
                try:
                    store.put_bytes(blob=job_paths.final("pdf"), data_bytes=pdf_bytes)
                except Exception:
                    logging.exception("Failed to upload PDF export for job %s", job_paths.job_id)
            docx_bytes = export_docx(final_text, {}, store, job_paths)
            if docx_bytes:
                try:
                    store.put_bytes(blob=job_paths.final("docx"), data_bytes=docx_bytes)
                except Exception as exc:
                    logging.exception("Failed to upload DOCX export for job %s", job_paths.job_id)
                    track_exception(exc, {"job_id": job_paths.job_id, "stage": "FINALIZE", "artifact": "docx"})
        except Exception as exc:
            logging.exception("Failed to finalize job %s", data.get("job_id"))
            track_exception(exc, {"job_id": job_paths.job_id, "stage": "FINALIZE"})
    final_tokens = 0
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "FINALIZE",
            timing,
            artifact=job_paths.final("md"),
            tokens=final_tokens,
            model=None,
            source=data,
        )
    )
