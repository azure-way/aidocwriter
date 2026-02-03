from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional, Mapping
import time

from .config import get_settings
from .agents.planner import PlannerAgent
from .agents.writer import WriterAgent
from .agents.reviewer import ReviewerAgent
from .agents.verifier import VerifierAgent
from .summary import Summarizer
from .graph import build_dependency_graph
from .storage import BlobStore, JobStoragePaths
from .telemetry import track_event, track_exception
from .agents.interviewer import InterviewerAgent
from .agents.style_reviewer import StyleReviewerAgent
from .agents.cohesion_reviewer import CohesionReviewerAgent
from .agents.summary_reviewer import SummaryReviewerAgent
from .messaging import send_queue_message, service_bus, publish_stage_event as messaging_publish_stage_event, publish_status as messaging_publish_status
from .workers import configure_logging as worker_configure_logging, run_processor as worker_run_processor
from .stages import core as stages_core
from .stages.diagram_prep import process_diagram_prep
from .models import StatusEvent
from docwriter.cycle_repository import ensure_cycle_state


@dataclass
class Job:
    title: str
    audience: str
    out: str = ""
    job_id: str | None = None
    cycles: int = 1
    user_id: str | None = None


def _sb_check():
    settings = get_settings()
    service_bus.ensure_ready()
    return settings


def _send(queue_name: str, payload: Dict[str, Any]) -> None:
    _sb_check()
    send_queue_message(queue_name, payload)


def _status(payload: Dict[str, Any]) -> None:
    _sb_check()
    messaging_publish_status(payload)


def _status_stage_event(
    stage: str,
    event: str,
    data: Mapping[str, Any],
    *,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    messaging_publish_stage_event(stage, event, data, extra=extra)


def send_job(job: Job) -> str:
    job_id = job.job_id or str(uuid.uuid4())
    if not job.user_id:
        raise ValueError("job.user_id is required to enqueue a job")
    job_paths = JobStoragePaths(user_id=job.user_id, job_id=job_id)
    try:
        store = BlobStore()
        blob_path = store.allocate_document_blob(job_id, job.user_id)
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "allocate_document_blob"})
        blob_path = job.out or job_paths.draft()
    payload = {
        "job_id": job_id,
        "title": job.title,
        "audience": job.audience,
        "out": blob_path,
        "cycles": max(1, int(job.cycles)),
        "user_id": job.user_id,
    }
    try:
        store = BlobStore()
        context_snapshot = {
            "job_id": job_id,
            "title": job.title,
            "audience": job.audience,
            "out": blob_path,
            "user_id": job.user_id,
        }
        store.put_text(
            blob=job_paths.intake("context.json"),
            text=json.dumps(context_snapshot, indent=2),
        )
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "write_initial_context"})
    settings = get_settings()
    _send(settings.sb_queue_plan_intake, payload)
    _status_stage_event(
        "PLAN_INTAKE",
        "QUEUED",
        payload,
    )
    _status(
        StatusEvent(
            job_id=job_id,
            stage="ENQUEUED",
            ts=time.time(),
            message=(
                f"stage completed: Job Submitted | stage document: {blob_path} | "
                "stage time: n/a | stage tokens: 0 | stage model: n/a | "
                f"stage notes: requested cycles {job.cycles}"
            ),
            artifact=blob_path,
            extra={
                "details": {
                    "duration_s": None,
                    "tokens": 0,
                    "model": None,
                    "artifact": blob_path,
                    "notes": f"requested cycles {job.cycles}",
                    "expected_cycles": job.cycles,
                    "cycles_remaining": job.cycles,
                    "cycles_completed": 0,
                },
                "user_id": job.user_id,
            },
        ).to_payload()
    )
    track_event(
        "job_enqueued",
        {
            "job_id": job_id,
            "stage": "PLAN_INTAKE",
            "cycles_remaining": str(job.cycles),
        },
    )
    return job_id

def send_resume(job_id: str, user_id: str | None = None) -> None:
    settings = get_settings()
    if not user_id:
        raise ValueError(f"user_id is required to resume job {job_id}")
    job_paths = JobStoragePaths(user_id=user_id, job_id=job_id)
    payload: Dict[str, Any] = {"job_id": job_id, "user_id": user_id}
    try:
        store = BlobStore()
        context_blob = job_paths.intake("context.json")
        context_text = store.get_text(blob=context_blob)
        context = json.loads(context_text)
        if isinstance(context, dict):
            payload.update(
                {
                    "title": context.get("title"),
                    "audience": context.get("audience"),
                    "out": context.get("out"),
                    "cycles": context.get("cycles"),
                    "user_id": context.get("user_id", user_id),
                }
            )
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "load_intake_context"})
    resolved_user_id = payload.get("user_id") or user_id
    if not isinstance(payload.get("out"), str) or not payload.get("out"):
        try:
            payload["out"] = BlobStore().allocate_document_blob(job_id, resolved_user_id)
        except Exception as exc:
            track_exception(exc, {"job_id": job_id, "operation": "allocate_document_blob_resume"})
            payload["out"] = JobStoragePaths(user_id=resolved_user_id, job_id=job_id).draft()
    
    ensure_cycle_state(payload)
    if payload.get("cycles") is None and payload.get("expected_cycles") is None:
        raise RuntimeError(f"Resume requested for job {job_id} without intake context")
    _send(settings.sb_queue_intake_resume, payload)
    _status_stage_event(
        "INTAKE_RESUME",
        "QUEUED",
        payload,
    )
    track_event("job_resume_signal", {"job_id": job_id})


# Exposed per-stage processors for E2E tests and direct invocation
def process_plan_intake(data: Dict[str, Any], interviewer: InterviewerAgent | None = None) -> None:
    stages_core.process_plan_intake(data, interviewer)


def process_intake_resume(data: Dict[str, Any]) -> None:
    stages_core.process_intake_resume(data)


def process_plan(data: Dict[str, Any], planner: PlannerAgent | None = None) -> None:
    stages_core.process_plan(data, planner)


def process_write(data: Dict[str, Any], writer: WriterAgent | None = None, summarizer: Summarizer | None = None) -> None:
    stages_core.process_write(data, writer, summarizer)


def process_review(data: Dict[str, Any], reviewer: ReviewerAgent | None = None) -> None:
    stages_core.process_review_general(data, reviewer)


def process_review_general(data: Dict[str, Any], reviewer: ReviewerAgent | None = None) -> None:
    stages_core.process_review_general(data, reviewer)


def process_review_style(data: Dict[str, Any], style_reviewer: StyleReviewerAgent | None = None) -> None:
    stages_core.process_review_style(data, style_reviewer)


def process_review_cohesion(data: Dict[str, Any], cohesion_reviewer: CohesionReviewerAgent | None = None) -> None:
    stages_core.process_review_cohesion(data, cohesion_reviewer)


def process_review_summary(data: Dict[str, Any], summary_reviewer: SummaryReviewerAgent | None = None) -> None:
    stages_core.process_review_summary(data, summary_reviewer)


def process_verify(data: Dict[str, Any], verifier: VerifierAgent | None = None) -> None:
    stages_core.process_verify(data, verifier)


def process_rewrite(data: Dict[str, Any], writer: WriterAgent | None = None) -> None:
    stages_core.process_rewrite(data, writer)


def process_finalize(data: Dict[str, Any]) -> None:
    stages_core.process_finalize(data)
