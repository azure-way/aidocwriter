from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict

try:
    from azure.servicebus import AutoLockRenewer  # type: ignore
except Exception:  # pragma: no cover
    AutoLockRenewer = None  # type: ignore

from docwriter.config import get_settings
from docwriter.diagram_renderer import process_diagram_render
from docwriter.messaging import service_bus
from docwriter.queue import (
    process_diagram_prep,
    process_finalize,
    process_intake_resume,
    process_plan,
    process_plan_intake,
    process_rewrite,
    process_review_cohesion,
    process_review_general,
    process_review_style,
    process_review_summary,
    process_verify,
    process_write,
)
from docwriter.status_store import get_status_table_store
from docwriter.telemetry import track_exception
from docwriter.workers import configure_logging

Processor = Callable[[Dict[str, Any]], None]

WORKER_KIND_QUEUE = "queue"
WORKER_KIND_TOPIC = "topic"

STAGE_HANDLERS: dict[str, Processor] = {
    "plan-intake": process_plan_intake,
    "intake-resume": process_intake_resume,
    "plan": process_plan,
    "write": process_write,
    "review-general": process_review_general,
    "review-style": process_review_style,
    "review-cohesion": process_review_cohesion,
    "review-summary": process_review_summary,
    "verify": process_verify,
    "rewrite": process_rewrite,
    "diagram-prep": process_diagram_prep,
    "diagram-render": process_diagram_render,
    "finalize": process_finalize,
    "status-writer": lambda data: get_status_table_store().record(data),
}


@dataclass(frozen=True)
class WorkerConfig:
    stage: str
    kind: str
    queue: str | None
    topic: str | None
    subscription: str | None
    max_messages_per_execution: int


def _read_config() -> WorkerConfig:
    stage = os.getenv("DOCWRITER_WORKER_STAGE", "").strip()
    if not stage:
        raise RuntimeError("DOCWRITER_WORKER_STAGE is required")
    if stage not in STAGE_HANDLERS:
        raise RuntimeError(f"Unsupported DOCWRITER_WORKER_STAGE: {stage}")

    kind = os.getenv("DOCWRITER_WORKER_KIND", WORKER_KIND_QUEUE).strip().lower()
    if kind not in {WORKER_KIND_QUEUE, WORKER_KIND_TOPIC}:
        raise RuntimeError(
            f"DOCWRITER_WORKER_KIND must be '{WORKER_KIND_QUEUE}' or '{WORKER_KIND_TOPIC}'"
        )

    queue = os.getenv("DOCWRITER_WORKER_QUEUE")
    topic = os.getenv("DOCWRITER_WORKER_TOPIC")
    subscription = os.getenv("DOCWRITER_WORKER_SUBSCRIPTION")

    raw_max_messages = os.getenv("DOCWRITER_MAX_MESSAGES_PER_EXECUTION", "1")
    try:
        max_messages_per_execution = int(raw_max_messages)
    except ValueError:
        max_messages_per_execution = 1
    if max_messages_per_execution != 1:
        logging.warning(
            "DOCWRITER_MAX_MESSAGES_PER_EXECUTION=%s ignored; forcing one message per execution",
            raw_max_messages,
        )
        max_messages_per_execution = 1

    if kind == WORKER_KIND_QUEUE and not queue:
        raise RuntimeError("DOCWRITER_WORKER_QUEUE is required for queue workers")
    if kind == WORKER_KIND_TOPIC and (not topic or not subscription):
        raise RuntimeError(
            "DOCWRITER_WORKER_TOPIC and DOCWRITER_WORKER_SUBSCRIPTION are required for topic workers"
        )

    return WorkerConfig(
        stage=stage,
        kind=kind,
        queue=queue,
        topic=topic,
        subscription=subscription,
        max_messages_per_execution=max_messages_per_execution,
    )


def _decode_message(message: Any) -> Dict[str, Any]:
    try:
        body = message.body
        raw = b"".join(part for part in body).decode("utf-8")
    except Exception:
        raw = str(message)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logging.exception("Unable to decode Service Bus message body: %s", raw)
        raise


def run_once(config: WorkerConfig) -> bool:
    settings = get_settings()
    service_bus.ensure_ready()
    handler = STAGE_HANDLERS[config.stage]
    client = service_bus.get_client()

    lock_renewer = None
    renew_seconds = getattr(settings, "sb_lock_renew_s", 0)
    if AutoLockRenewer is not None and renew_seconds and renew_seconds > 0:
        lock_renewer = AutoLockRenewer(max_lock_renewal_duration=renew_seconds)

    receiver_context = (
        client.get_queue_receiver(queue_name=config.queue, max_wait_time=30)
        if config.kind == WORKER_KIND_QUEUE
        else client.get_subscription_receiver(
            topic_name=config.topic,
            subscription_name=config.subscription,
            max_wait_time=30,
        )
    )

    try:
        with receiver_context as receiver:
            messages = receiver.receive_messages(max_message_count=1, max_wait_time=30)
            if not messages:
                logging.info("No message available for stage %s", config.stage)
                return False
            message = messages[0]

            if lock_renewer is not None:
                lock_renewer.register(
                    receiver,
                    message,
                    max_lock_renewal_duration=renew_seconds,
                )

            data = _decode_message(message)
            data["_renew_lock"] = lambda: receiver.renew_message_lock(message)
            try:
                handler(data)
                receiver.complete_message(message)
                logging.info("Stage %s processed message %s", config.stage, message.message_id)
                return True
            except Exception:
                receiver.abandon_message(message)
                raise
    except Exception as exc:
        track_exception(exc, {"worker_stage": config.stage, "worker_kind": config.kind})
        logging.exception("Worker stage %s failed", config.stage)
        raise
    finally:
        if lock_renewer is not None:
            lock_renewer.close()


def main() -> int:
    config = _read_config()
    configure_logging(f"job-{config.stage}")
    try:
        processed = run_once(config)
        return 0 if processed else 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
