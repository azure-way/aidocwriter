from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Mapping, Optional, Set, Union

try:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage  # type: ignore
except Exception:  # pragma: no cover
    ServiceBusClient = None  # type: ignore
    ServiceBusMessage = None  # type: ignore

from .config import get_settings
from .models import StatusEvent
from .telemetry import track_event, track_exception


class ServiceBusManager:
    """Manage Service Bus connections and normalized status publishing."""

    _client: ServiceBusClient | None = None  # type: ignore[assignment]
    _connection: str | None = None

    def __init__(self) -> None:
        self._status_defaults: Set[str] = {
            "aidocwriter-status",
            "docwriter-status",
        }

    def ensure_ready(self) -> None:
        settings = get_settings()
        if not settings.sb_connection_string:
            raise RuntimeError("SERVICE_BUS_CONNECTION_STRING not set")
        if ServiceBusClient is None or ServiceBusMessage is None:  # pragma: no cover
            raise RuntimeError("azure-servicebus not installed")
        if self._client is None or self._connection != settings.sb_connection_string:
            self._client = ServiceBusClient.from_connection_string(settings.sb_connection_string)
            self._connection = settings.sb_connection_string

    def get_client(self) -> ServiceBusClient:
        self.ensure_ready()
        assert self._client is not None  # for type-checkers
        return self._client

    # Queue interactions -------------------------------------------------
    def send_queue(self, queue_name: str, payload: Dict[str, Any]) -> None:
        self.ensure_ready()
        settings = get_settings()
        client = self.get_client()
        try:
            with client.get_queue_sender(queue_name) as sender:
                sender.send_messages(ServiceBusMessage(json.dumps(payload)))
        except Exception as exc:
            track_exception(exc, {"queue": queue_name})
            raise

    # Status topic -------------------------------------------------------
    def publish_status(self, payload: Union[StatusEvent, Dict[str, Any]]) -> None:
        if isinstance(payload, StatusEvent):
            payload = payload.to_payload()
        self.ensure_ready()
        _ensure_status_message(payload)
        topics = self._status_topics()
        client = self.get_client()
        sent = False
        last_exc: Exception | None = None
        for topic in topics:
            try:
                with client.get_topic_sender(topic) as sender:
                    sender.send_messages(ServiceBusMessage(json.dumps(payload)))
                sent = True
                break
            except Exception as exc:
                last_exc = exc
                track_exception(exc, {"topic": topic})
        if not sent and last_exc:
            logging.error("Failed to publish status event to Service Bus: %s", last_exc)
        props = {k: str(v) for k, v in payload.items() if isinstance(v, (str, int, float))}
        if "job_id" in payload:
            props["job_id"] = str(payload["job_id"])
        track_event("job_status", props)

    def publish_stage_event(
        self,
        stage: str,
        event: str,
        data: Mapping[str, Any],
        *,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> None:
        job_id = data.get("job_id")
        if not job_id:
            return
        payload: Dict[str, Any] = {}
        if extra:
            for key, value in extra.items():
                if key in _ALLOWED_STATUS_EXTRA_KEYS and value is not None:
                    payload[key] = value
        cycle = _current_cycle(data) if stage in _CYCLIC_STAGES else None
        event_payload = StatusEvent(
            job_id=job_id,
            stage=f"{stage}_{event}",
            ts=time.time(),
            message=_build_default_message(f"{stage}_{event}", cycle),
            cycle=cycle,
            extra=payload,
        )
        self.publish_status(event_payload.to_payload())

    def _status_topics(self) -> List[str]:
        settings = get_settings()
        topics: List[str] = []
        primary = settings.sb_topic_status
        if primary:
            topics.append(primary)
        fallback_env = os.getenv("DOCWRITER_FALLBACK_STATUS_TOPIC")
        if fallback_env and fallback_env not in topics:
            topics.append(fallback_env)
        for default in self._status_defaults:
            if default not in topics:
                topics.append(default)
        return topics


_CYCLIC_STAGES: Set[str] = {"REVIEW", "VERIFY", "REWRITE"}
_ALLOWED_STATUS_EXTRA_KEYS: Set[str] = {
    "artifact",
    "message",
    "has_contradictions",
    "style_issues",
    "cohesion_issues",
    "placeholder_sections",
}


def _current_cycle(data: Mapping[str, Any]) -> Optional[int]:
    try:
        return int(data.get("cycles_completed", 0)) + 1
    except Exception:
        return None


def _format_stage_label(stage: Any) -> str:
    if not isinstance(stage, str) or not stage:
        return "Status update"
    parts = stage.split("_")
    if not parts:
        return "Status update"
    words = [parts[0].capitalize()] + [p.lower() for p in parts[1:]]
    return " ".join(words)


def _ensure_status_message(payload: Dict[str, Any]) -> None:
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return
    stage_label = _format_stage_label(payload.get("stage"))
    if "cycle" in payload and payload.get("cycle") is not None:
        payload["message"] = f"{stage_label} (cycle {payload['cycle']})"
    else:
        payload["message"] = stage_label


def _build_default_message(stage: str, cycle: Optional[int]) -> str:
    label = _format_stage_label(stage)
    if cycle is not None:
        return f"{label} (cycle {cycle})"
    return label


service_bus = ServiceBusManager()


def send_queue_message(queue_name: str, payload: Dict[str, Any]) -> None:
    service_bus.send_queue(queue_name, payload)


def publish_status(payload: Dict[str, Any]) -> None:
    service_bus.publish_status(payload)


def publish_stage_event(
    stage: str,
    event: str,
    data: Mapping[str, Any],
    *,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    service_bus.publish_stage_event(stage, event, data, extra=extra)
