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
from .storage import BlobStore
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
from .stages.cycles import CycleState


@dataclass
class Job:
    title: str
    audience: str
    out: str = ""
    job_id: str | None = None
    cycles: int = 1


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
    try:
        store = BlobStore()
        blob_path = store.allocate_document_blob(job_id)
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "allocate_document_blob"})
        blob_path = job.out or f"/tmp/{job_id}_document.md"
    payload = {
        "job_id": job_id,
        "title": job.title,
        "audience": job.audience,
        "out": blob_path,
        "cycles": max(1, int(job.cycles)),
        "cycles_remaining": max(1, int(job.cycles)),
        "cycles_completed": 0,
    }
    try:
        store = BlobStore()
        context_snapshot = {
            "job_id": job_id,
            "title": job.title,
            "audience": job.audience,
            "out": blob_path,
            "cycles": payload["cycles"],
            "cycles_remaining": payload["cycles_remaining"],
            "cycles_completed": payload["cycles_completed"],
        }
        store.put_text(
            blob=f"jobs/{job_id}/intake/context.json",
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
                    "cycles_remaining": payload["cycles_remaining"],
                    "cycles_completed": payload["cycles_completed"],
                }
            },
        ).to_payload()
    )
    track_event(
        "job_enqueued",
        {
            "job_id": job_id,
            "stage": "PLAN_INTAKE",
            "cycles_remaining": str(payload["cycles_remaining"]),
        },
    )
    return job_id


def worker_plan_intake() -> None:
    settings = _sb_check()
    interviewer = InterviewerAgent()

    def handle(_msg, data: Dict[str, Any]):
        process_plan_intake(data, interviewer)
    _run_processor(settings.sb_queue_plan_intake, handle, stage_name="PLAN_INTAKE")


def worker_intake_resume() -> None:
    settings = _sb_check()

    def handle(_msg, data: Dict[str, Any]):
        process_intake_resume(data)

    _run_processor(settings.sb_queue_intake_resume, handle, stage_name="INTAKE_RESUME")


def send_resume(job_id: str) -> None:
    settings = get_settings()
    payload: Dict[str, Any] = {"job_id": job_id}
    try:
        store = BlobStore()
        context_text = store.get_text(blob=f"jobs/{job_id}/intake/context.json")
        context = json.loads(context_text)
        if isinstance(context, dict):
            payload.update(
                {
                    "title": context.get("title"),
                    "audience": context.get("audience"),
                    "out": context.get("out"),
                    "cycles": context.get("cycles"),
                    "cycles_remaining": context.get("cycles_remaining"),
                    "cycles_completed": context.get("cycles_completed"),
                }
            )
    except Exception as exc:
        track_exception(exc, {"job_id": job_id, "operation": "load_intake_context"})
    if not isinstance(payload.get("out"), str) or not payload.get("out"):
        try:
            payload["out"] = BlobStore().allocate_document_blob(job_id)
        except Exception as exc:
            track_exception(exc, {"job_id": job_id, "operation": "allocate_document_blob_resume"})
            payload["out"] = f"/tmp/{job_id}_document.md"
    if payload.get("cycles") is None and payload.get("expected_cycles") is None:
        raise RuntimeError(f"Resume requested for job {job_id} without intake context")
    CycleState.from_context(payload).apply(payload)
    _send(settings.sb_queue_intake_resume, payload)
    _status_stage_event(
        "INTAKE_RESUME",
        "QUEUED",
        payload,
    )
    track_event("job_resume_signal", {"job_id": job_id})


def worker_plan() -> None:
    worker_configure_logging("worker-plan")
    settings = _sb_check()
    planner = PlannerAgent()

    def handle(_msg, data: Dict[str, Any]):
        process_plan(data, planner)

    worker_run_processor(settings.sb_queue_plan, handle, stage_name="PLAN")


def worker_write() -> None:
    worker_configure_logging("worker-write")
    settings = _sb_check()
    writer = WriterAgent()
    summarizer = Summarizer()

    def handle(_msg, data: Dict[str, Any]):
        process_write(data, writer, summarizer)

    worker_run_processor(settings.sb_queue_write, handle, stage_name="WRITE")


def worker_review() -> None:
    worker_configure_logging("worker-review")
    settings = _sb_check()
    reviewer = ReviewerAgent()

    def handle(_msg, data: Dict[str, Any]):
        process_review(data, reviewer)

    worker_run_processor(settings.sb_queue_review, handle, stage_name="REVIEW")


def worker_verify() -> None:
    worker_configure_logging("worker-verify")
    settings = _sb_check()
    verifier = VerifierAgent()

    def handle(_msg, data: Dict[str, Any]):
        process_verify(data, verifier)

    worker_run_processor(settings.sb_queue_verify, handle, stage_name="VERIFY")


def worker_rewrite() -> None:
    worker_configure_logging("worker-rewrite")
    settings = _sb_check()
    writer = WriterAgent()

    def handle(_msg, data: Dict[str, Any]):
        process_rewrite(data, writer)

    worker_run_processor(settings.sb_queue_rewrite, handle, stage_name="REWRITE")


def worker_diagram_prep() -> None:
    worker_configure_logging("worker-diagram-prep")
    settings = _sb_check()

    def handle(_msg, data: Dict[str, Any]):
        process_diagram_prep(data)

    worker_run_processor(settings.sb_queue_diagram_prep, handle, stage_name="DIAGRAM")


def worker_finalize() -> None:
    worker_configure_logging("worker-finalize")
    settings = _sb_check()

    def handle(_msg, data: Dict[str, Any]):
        process_finalize(data)

    worker_run_processor(settings.sb_queue_finalize_ready, handle, stage_name="FINALIZE")


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
    stages_core.process_review(data, reviewer)


def process_verify(data: Dict[str, Any], verifier: VerifierAgent | None = None) -> None:
    stages_core.process_verify(data, verifier)


def process_rewrite(data: Dict[str, Any], writer: WriterAgent | None = None) -> None:
    stages_core.process_rewrite(data, writer)


def process_finalize(data: Dict[str, Any]) -> None:
    stages_core.process_finalize(data)
