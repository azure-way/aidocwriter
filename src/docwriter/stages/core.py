from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from docwriter.agents.cohesion_reviewer import CohesionReviewerAgent
from docwriter.agents.interviewer import InterviewerAgent
from docwriter.agents.planner import PlannerAgent
from docwriter.agents.reviewer import ReviewerAgent
from docwriter.agents.style_reviewer import StyleReviewerAgent
from docwriter.agents.summary_reviewer import SummaryReviewerAgent
from docwriter.agents.verifier import VerifierAgent
from docwriter.agents.writer import WriterAgent
from docwriter.artifacts import export_docx, export_pdf, replace_mermaid_with_images
from docwriter.config import get_settings
from docwriter.graph import build_dependency_graph
from docwriter.messaging import publish_stage_event, publish_status, send_queue_message
from docwriter.models import StatusEvent
from docwriter.stage_utils import (
    find_placeholder_sections,
    merge_revised_markdown,
    parse_review_guidance,
)
from docwriter.storage import BlobStore
from docwriter.summary import Summarizer
from docwriter.telemetry import stage_timer, track_event, track_exception, StageTiming

import tiktoken

ENCODING_NAME = "cl100k_base"

logger = logging.getLogger(__name__)


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


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    extra = {"details": details} if details else {}
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
    artifact_path = f"jobs/{data['job_id']}/intake/questions.json"
    with stage_timer(job_id=data["job_id"], stage="PLAN_INTAKE") as timing:
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
                "cycles_remaining": data.get("cycles_remaining"),
                "cycles_completed": data.get("cycles_completed"),
            }
            store.put_text(
                blob=f"jobs/{data['job_id']}/intake/context.json",
                text=json.dumps(context_snapshot, indent=2),
            )
            sample_answers = {
                str(item.get("id")): item.get("sample", "") for item in questions if isinstance(item, dict)
            }
            store.put_text(
                blob=f"jobs/{data['job_id']}/intake/sample_answers.json",
                text=json.dumps(sample_answers, indent=2),
            )
        except Exception as exc:
            track_exception(exc, {"job_id": data["job_id"], "stage": "PLAN_INTAKE"})
    question_tokens = _usage_total(getattr(interviewer.llm, "last_usage", None))
    if not question_tokens:
        question_tokens = _estimate_tokens(json.dumps(questions, ensure_ascii=False))
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
            extra={
                "details": {
                    "duration_s": timing.duration_s,
                    "tokens": question_tokens,
                    "model": settings.planner_model,
                    "artifact": artifact_path,
                    "notes": "upload answers.json and resume",
                }
            },
        )
    )


def process_intake_resume(data: Dict[str, Any]) -> None:
    settings = get_settings()
    with stage_timer(job_id=data["job_id"], stage="INTAKE_RESUME") as timing:
        publish_stage_event("PLAN", "QUEUED", data)
        send_queue_message(settings.sb_queue_plan, data)
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
                extra={
                    "details": {
                        "duration_s": timing.duration_s,
                        "tokens": 0,
                        "model": None,
                        "artifact": None,
                    }
                },
            )
        )


def process_plan(data: Dict[str, Any], planner: PlannerAgent | None = None) -> None:
    settings = get_settings()
    planner = planner or PlannerAgent()
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
    with stage_timer(job_id=data["job_id"], stage="PLAN") as timing:
        audience = data.get("audience")
        title = data.get("title")
        length_pages = 80

        answers: Dict[str, Any] = {}
        if store:
            try:
                plan_text = store.get_text(blob=f"jobs/{data['job_id']}/plan.json")
                existing_plan = json.loads(plan_text)
                title = existing_plan.get("title", title)
                audience = existing_plan.get("audience", audience)
                if existing_plan.get("length_pages") is not None:
                    length_pages = int(existing_plan.get("length_pages"))
            except Exception:
                pass

            try:
                answers_text = store.get_text(blob=f"jobs/{data['job_id']}/intake/answers.json")
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
            "length_pages": max(60, plan.length_pages or 80),
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
        target_store.put_text(
            blob=f"jobs/{data['job_id']}/plan.json",
            text=json.dumps(payload["plan"], indent=2),
        )
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "PLAN"})
    publish_stage_event("WRITE", "QUEUED", payload)
    send_queue_message(settings.sb_queue_write, payload)
    artifact_path = f"jobs/{data['job_id']}/plan.json"
    plan_tokens = _usage_total(getattr(planner.llm, "last_usage", None))
    if not plan_tokens:
        plan_tokens = _estimate_tokens(json.dumps(payload["plan"], ensure_ascii=False))
    publish_status(
        StatusEvent(
            job_id=data["job_id"],
            stage="PLAN_DONE",
            ts=time.time(),
            message=_build_stage_message(
                "Plan",
                artifact_path,
                timing.duration_s,
                plan_tokens,
                settings.planner_model,
            ),
            artifact=artifact_path,
            extra={
                "details": {
                    "duration_s": timing.duration_s,
                    "tokens": plan_tokens,
                    "model": settings.planner_model,
                    "artifact": artifact_path,
                }
            },
        )
    )
    print("[worker-plan] Dispatched job", data.get("job_id"), "to writing queue")


def process_write(data: Dict[str, Any], writer: WriterAgent | None = None, summarizer: Summarizer | None = None) -> None:
    settings = get_settings()
    writer = writer or WriterAgent()
    summarizer = summarizer or Summarizer()
    blob_path = data.get("out")
    if not isinstance(blob_path, str) or not blob_path:
        blob_path = BlobStore().allocate_document_blob(data["job_id"])

    write_tokens_total = 0
    with stage_timer(job_id=data["job_id"], stage="WRITE") as timing:
        plan = data["plan"]
        outline = plan.get("outline", [])
        graph = build_dependency_graph(outline)
        order = graph.topological_order() if outline else []
        id_to_section = {str(s.get("id")): s for s in outline}
        dependency_summaries = data.get("dependency_summaries", {})
        document_text_parts: list[str] = []
        for sid in order:
            section = id_to_section[sid]
            deps = section.get("dependencies", []) or []
            dep_context = "\n".join([dependency_summaries.get(str(d), "") for d in deps if dependency_summaries.get(str(d))])
            section_output = "".join(list(writer.write_section(plan=plan, section=section, dependency_context=dep_context)))
            document_text_parts.append(section_output)
            summary = summarizer.summarize_section("\n\n".join(document_text_parts))
            dependency_summaries[sid] = summary
            write_tokens_total += _usage_total(getattr(writer.llm, "last_usage", None))
        document_text = "\n\n".join(document_text_parts)
    payload = {**data, "out": blob_path, "dependency_summaries": dependency_summaries}
    try:
        store = BlobStore()
        store.put_text(blob=blob_path, text=document_text)
        store.put_text(blob=f"jobs/{data['job_id']}/draft.md", text=document_text)
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "WRITE"})
    publish_stage_event("REVIEW", "QUEUED", payload)
    send_queue_message(settings.sb_queue_review, payload)
    if not write_tokens_total:
        write_tokens_total = _estimate_tokens(document_text)
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "WRITE",
            timing,
            artifact=f"jobs/{data['job_id']}/draft.md",
            tokens=write_tokens_total,
            model=settings.writer_model,
        )
    )


def process_review(data: Dict[str, Any], reviewer: ReviewerAgent | None = None) -> None:
    settings = get_settings()
    reviewer = reviewer or ReviewerAgent()
    with stage_timer(job_id=data["job_id"], stage="REVIEW", cycle=int(data.get("cycles_completed", 0)) + 1) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        review_json = reviewer.review(plan=data["plan"], draft_markdown=draft)
        style_agent = StyleReviewerAgent()
        style = style_agent.review_style(plan=data["plan"], markdown=draft)
        cohesion_agent = CohesionReviewerAgent()
        cohesion = cohesion_agent.review_cohesion(plan=data["plan"], markdown=draft)
        summary_agent = SummaryReviewerAgent()
        summary = summary_agent.review_executive_summary(plan=data["plan"], markdown=draft)
        cycle_idx = int(data.get("cycles_completed", 0)) + 1
    payload = {**data, "review_json": review_json, "style_json": style, "cohesion_json": cohesion, "exec_summary_json": summary}
    try:
        store = BlobStore()
        store.put_text(
            blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/review.json",
            text=review_json,
        )
        store.put_text(blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/style.json", text=style)
        store.put_text(blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/cohesion.json", text=cohesion)
        store.put_text(blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/executive_summary.json", text=summary)
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "REVIEW"})
    publish_stage_event("VERIFY", "QUEUED", payload)
    send_queue_message(settings.sb_queue_verify, payload)
    review_tokens = _usage_total(getattr(reviewer.llm, "last_usage", None))
    review_tokens += _usage_total(getattr(style_agent.llm, "last_usage", None))
    review_tokens += _usage_total(getattr(cohesion_agent.llm, "last_usage", None))
    review_tokens += _usage_total(getattr(summary_agent.llm, "last_usage", None))
    if not review_tokens:
        review_tokens = sum(
            _estimate_tokens(text)
            for text in (review_json, style, cohesion, summary)
            if isinstance(text, str)
        )
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "REVIEW",
            timing,
            artifact=f"jobs/{data['job_id']}/cycle_{cycle_idx}/review.json",
            tokens=review_tokens,
            model=settings.reviewer_model,
        )
    )


def process_verify(data: Dict[str, Any], verifier: VerifierAgent | None = None) -> None:
    settings = get_settings()
    verifier = verifier or VerifierAgent()
    with stage_timer(job_id=data["job_id"], stage="VERIFY", cycle=int(data.get("cycles_completed", 0)) + 1) as timing:
        store = BlobStore()
        draft = store.get_text(blob=data["out"])
        cycle_idx = int(data.get("cycles_completed", 0)) + 1
        try:
            review_data = json.loads(data.get("review_json", "{}"))
            revised = review_data.get("revised_markdown")
            if isinstance(revised, str) and revised.strip():
                merged = merge_revised_markdown(draft, revised)
                if merged != draft:
                    draft = merged
                    try:
                        store.put_text(blob=data["out"], text=merged)
                        store.put_text(
                            blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/revision.md",
                            text=merged,
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        placeholder_sections = find_placeholder_sections(draft)
        verification_json = verifier.verify(
            dependency_summaries=data.get("dependency_summaries", {}), final_markdown=draft
        )
    payload = {**data, "verification_json": verification_json}
    try:
        store = BlobStore()
        store.put_text(
            blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/contradictions.json",
            text=verification_json,
        )
    except Exception as exc:
        track_exception(exc, {"job_id": data["job_id"], "stage": "VERIFY"})
    try:
        verification = json.loads(verification_json)
        contradictions = verification.get("contradictions", [])
    except Exception:
        contradictions = []

    style_guidance, style_sections = parse_review_guidance(data.get("style_json"))
    cohesion_guidance, cohesion_sections = parse_review_guidance(data.get("cohesion_json"))
    needs_rewrite = (
        bool(contradictions)
        or bool(style_guidance)
        or bool(cohesion_guidance)
        or bool(placeholder_sections)
    )

    raw_cycles_remaining = payload.get("cycles_remaining")
    remaining_cycles = _coerce_int(raw_cycles_remaining, default=_coerce_int(data.get("cycles_remaining")))
    payload["cycles_remaining"] = remaining_cycles
    cycles_completed = _coerce_int(payload.get("cycles_completed", data.get("cycles_completed", 0)))
    payload["cycles_completed"] = cycles_completed

    if needs_rewrite:
        if remaining_cycles <= 0 and cycles_completed == 0:
            logger.warning(
                "Job %s needs rewrite but has %r cycles remaining; granting a single additional cycle.",
                data.get("job_id"),
                raw_cycles_remaining,
            )
            remaining_cycles = 1
            payload["cycles_remaining"] = remaining_cycles
        if remaining_cycles > 0:
            payload["placeholder_sections"] = sorted(placeholder_sections)
            publish_stage_event("REWRITE", "QUEUED", payload)
            send_queue_message(settings.sb_queue_rewrite, payload)
            # Early return so we do not fall through to finalize scheduling.
            return
    # No rewrite (either not needed or no cycles left)
    payload["placeholder_sections"] = []
        publish_stage_event("FINALIZE", "QUEUED", payload)
        send_queue_message(settings.sb_queue_finalize, payload)
    artifact_path = f"jobs/{data['job_id']}/cycle_{cycle_idx}/contradictions.json"
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
                "details": {
                    "duration_s": timing.duration_s,
                    "tokens": verify_tokens,
                    "model": settings.reviewer_model,
                    "artifact": artifact_path,
                }
            },
        )
    )


def process_rewrite(data: Dict[str, Any], writer: WriterAgent | None = None) -> None:
    settings = get_settings()
    writer = writer or WriterAgent()
    rewrite_tokens_total = 0
    with stage_timer(job_id=data["job_id"], stage="REWRITE", cycle=int(data.get("cycles_completed", 0)) + 1) as timing:
        plan = data["plan"]
        store = BlobStore()
        text = store.get_text(blob=data["out"])
        cycle_idx = int(data.get("cycles_completed", 0)) + 1
        try:
            verification = json.loads(data.get("verification_json", "{}"))
        except Exception:
            verification = {"contradictions": []}
        contradictions = verification.get("contradictions", [])
        id_to_section = {str(s.get("id")): s for s in plan.get("outline", [])}
        dependency_summaries = data.get("dependency_summaries", {})

        style_guidance, style_sections = parse_review_guidance(data.get("style_json"))
        cohesion_guidance, cohesion_sections = parse_review_guidance(data.get("cohesion_json"))
        combined_guidance = "\n".join(filter(None, [style_guidance, cohesion_guidance]))

        affected = {str(c.get("section_id")) for c in contradictions if c.get("section_id")}
        affected.update(style_sections)
        affected.update(cohesion_sections)

        if not affected and combined_guidance:
            affected = set(id_to_section.keys())

        placeholder_sections = {str(s) for s in data.get("placeholder_sections", [])}
        affected.update(placeholder_sections)

        if affected:
            for sid in affected:
                section = id_to_section.get(sid)
                if not section:
                    continue
                deps = section.get("dependencies", []) or []
                dep_context = "\n".join(
                    [dependency_summaries.get(str(d), "") for d in deps if dependency_summaries.get(str(d))]
                )
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
                start_marker = f"<!-- SECTION:{sid}:START -->"
                end_marker = f"<!-- SECTION:{sid}:END -->"
                start_idx = text.find(start_marker)
                end_idx = text.find(end_marker)
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    end_idx += len(end_marker)
                    text = text[:start_idx] + new_text + text[end_idx:]
                rewrite_tokens_total += _usage_total(getattr(writer.llm, "last_usage", None))
            store.put_text(blob=data["out"], text=text)
            try:
                store.put_text(blob=f"jobs/{data['job_id']}/cycle_{cycle_idx}/rewrite.md", text=text)
            except Exception:
                pass
    payload = {
        **data,
        "cycles_remaining": max(0, int(data.get("cycles_remaining", 0)) - 1),
        "cycles_completed": int(data.get("cycles_completed", 0)) + 1,
        "placeholder_sections": [],
    }
    publish_stage_event("REVIEW", "QUEUED", payload)
    send_queue_message(settings.sb_queue_review, payload)
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
        )
    )


def process_finalize(data: Dict[str, Any]) -> None:
    final_text = ""
    with stage_timer(job_id=data["job_id"], stage="FINALIZE") as timing:
        try:
            store = BlobStore()
            job_id = data["job_id"]
            target_blob = data["out"]
            final_text = store.get_text(blob=target_blob)
            final_text, image_map = replace_mermaid_with_images(final_text, job_id, store)
            store.put_text(blob=f"jobs/{job_id}/final.md", text=final_text)
            pdf_bytes = export_pdf(final_text, image_map, store, job_id)
            if pdf_bytes:
                try:
                    store.put_bytes(blob=f"jobs/{job_id}/final.pdf", data_bytes=pdf_bytes)
                except Exception:
                    logging.exception("Failed to upload PDF export for job %s", job_id)
            docx_bytes = export_docx(final_text, image_map, store, job_id)
            if docx_bytes:
                try:
                    store.put_bytes(blob=f"jobs/{job_id}/final.docx", data_bytes=docx_bytes)
                except Exception:
                    logging.exception("Failed to upload DOCX export for job %s", job_id)
        except Exception:
            logging.exception("Failed to finalize job %s", data.get("job_id"))
    final_tokens = 0
    publish_status(
        _stage_completed_event(
            data["job_id"],
            "FINALIZE",
            timing,
            artifact=f"jobs/{data['job_id']}/final.md",
            tokens=final_tokens,
            model=None,
        )
    )
