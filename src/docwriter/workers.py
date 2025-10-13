from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

try:
    from azure.servicebus import AutoLockRenewer  # type: ignore
except Exception:  # pragma: no cover
    AutoLockRenewer = None  # type: ignore

from .config import get_settings
from .messaging import publish_stage_event, service_bus
from .telemetry import track_exception

WorkerHandler = Callable[[Any, Dict[str, Any]], None]

LOG_CONFIGURED = False


def configure_logging(worker_name: str) -> None:
    global LOG_CONFIGURED
    if LOG_CONFIGURED:
        return
    log_level = os.getenv("DOCWRITER_LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handlers: list[logging.Handler] = []

    log_dir = os.getenv("LOG_DIR")
    if log_dir:
        log_path = os.getenv("LOG_DIR")
        if log_path:
            path = os.path.abspath(log_path)
            os.makedirs(path, exist_ok=True)
            file_handler = logging.FileHandler(os.path.join(path, f"{worker_name}.log"))
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)
    LOG_CONFIGURED = True


def run_processor(
    queue_name: str,
    handler: WorkerHandler,
    *,
    max_workers: int = 1,
    stage_name: Optional[str] = None,
) -> None:
    settings = get_settings()
    service_bus.ensure_ready()

    renew_seconds = getattr(settings, "sb_lock_renew_s", 0)
    lock_renewer = None
    if AutoLockRenewer is not None and renew_seconds and renew_seconds > 0:
        lock_renewer = AutoLockRenewer(max_lock_renewal_duration=renew_seconds)

    client = service_bus.get_client()
    try:
        with client.get_queue_receiver(queue_name, max_wait_time=30) as receiver:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                while True:
                    try:
                        messages = receiver.receive_messages(max_message_count=10, max_wait_time=30)
                    except Exception as exc:
                        track_exception(exc, {"queue": queue_name, "operation": "receive_messages"})
                        time.sleep(2)
                        continue
                    if not messages:
                        continue
                    for msg in messages:
                        try:
                            data = _decode_message(msg)
                        except Exception as exc:
                            track_exception(
                                exc,
                                {
                                    "queue": queue_name,
                                    "operation": "decode",
                                    "message_id": str(getattr(msg, "message_id", "")),
                                },
                            )
                            receiver.abandon_message(msg)
                            continue
                        if stage_name:
                            try:
                                publish_stage_event(stage_name, "START", data)
                            except Exception:
                                logging.exception("Failed to emit stage start event for %s", stage_name)
                        if lock_renewer is not None:
                            try:
                                lock_renewer.register(
                                    receiver,
                                    msg,
                                    max_lock_renewal_duration=renew_seconds,
                                )
                            except Exception as renew_exc:
                                logging.exception(
                                    "Failed to register auto lock renewal for message %s: %s",
                                    msg.message_id,
                                    renew_exc,
                                )
                                track_exception(
                                    renew_exc,
                                    {
                                        "queue": queue_name,
                                        "operation": "lock_renew",
                                        "message_id": str(getattr(msg, "message_id", "")),
                                    },
                                )
                        fut = pool.submit(handler, msg, data)
                        try:
                            fut.result()
                            receiver.complete_message(msg)
                        except Exception as exc:
                            logging.exception(
                                "Message processing failed, abandoning message %s: %s",
                                msg.message_id,
                                exc,
                            )
                            track_exception(
                                exc,
                                {
                                    "queue": queue_name,
                                    "operation": "handler",
                                    "message_id": str(getattr(msg, "message_id", "")),
                                },
                            )
                            receiver.abandon_message(msg)
    finally:
        if lock_renewer is not None:
            lock_renewer.close()


def _decode_message(msg) -> Dict[str, Any]:
    import json

    try:
        return json.loads(str(msg))
    except Exception:
        return json.loads("".join([b.decode("utf-8") for b in msg.body]))
