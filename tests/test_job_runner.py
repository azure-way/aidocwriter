from __future__ import annotations

import json

import pytest

from docwriter import job_runner


class _FakeMessage:
    def __init__(self, payload: dict, message_id: str = "m1"):
        self.body = [json.dumps(payload).encode("utf-8")]
        self.message_id = message_id


class _FakeReceiver:
    def __init__(self, messages: list[_FakeMessage]):
        self._messages = messages
        self.completed: list[str] = []
        self.abandoned: list[str] = []
        self.renewed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def receive_messages(self, max_message_count: int, max_wait_time: int):
        assert max_message_count == 1
        return self._messages

    def complete_message(self, message: _FakeMessage) -> None:
        self.completed.append(message.message_id)

    def abandon_message(self, message: _FakeMessage) -> None:
        self.abandoned.append(message.message_id)

    def renew_message_lock(self, message: _FakeMessage) -> None:
        self.renewed.append(message.message_id)


class _FakeClient:
    def __init__(self, receiver: _FakeReceiver):
        self.receiver = receiver
        self.queue_calls: list[str] = []
        self.subscription_calls: list[tuple[str, str]] = []

    def get_queue_receiver(self, queue_name: str, max_wait_time: int):
        self.queue_calls.append(queue_name)
        return self.receiver

    def get_subscription_receiver(
        self,
        topic_name: str,
        subscription_name: str,
        max_wait_time: int,
    ):
        self.subscription_calls.append((topic_name, subscription_name))
        return self.receiver


def test_read_config_forces_one_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCWRITER_WORKER_STAGE", "plan")
    monkeypatch.setenv("DOCWRITER_WORKER_KIND", "queue")
    monkeypatch.setenv("DOCWRITER_WORKER_QUEUE", "docwriter-plan")
    monkeypatch.setenv("DOCWRITER_MAX_MESSAGES_PER_EXECUTION", "10")

    cfg = job_runner._read_config()

    assert cfg.max_messages_per_execution == 1


def test_run_once_queue_dispatches_and_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []
    message = _FakeMessage({"job_id": "j1"})
    receiver = _FakeReceiver([message])
    client = _FakeClient(receiver)

    monkeypatch.setattr(job_runner.service_bus, "ensure_ready", lambda: None)
    monkeypatch.setattr(job_runner.service_bus, "get_client", lambda: client)
    monkeypatch.setattr(job_runner, "AutoLockRenewer", None)
    monkeypatch.setattr(
        job_runner,
        "STAGE_HANDLERS",
        {"plan": lambda data: seen.append(data)},
    )

    cfg = job_runner.WorkerConfig(
        stage="plan",
        kind="queue",
        queue="docwriter-plan",
        topic=None,
        subscription=None,
        max_messages_per_execution=1,
    )

    processed = job_runner.run_once(cfg)

    assert processed is True
    assert client.queue_calls == ["docwriter-plan"]
    assert receiver.completed == ["m1"]
    assert seen and seen[0]["job_id"] == "j1"


def test_run_once_topic_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _FakeMessage({"job_id": "j2"})
    receiver = _FakeReceiver([message])
    client = _FakeClient(receiver)

    monkeypatch.setattr(job_runner.service_bus, "ensure_ready", lambda: None)
    monkeypatch.setattr(job_runner.service_bus, "get_client", lambda: client)
    monkeypatch.setattr(job_runner, "AutoLockRenewer", None)
    monkeypatch.setattr(job_runner, "STAGE_HANDLERS", {"status-writer": lambda data: None})

    cfg = job_runner.WorkerConfig(
        stage="status-writer",
        kind="topic",
        queue=None,
        topic="aidocwriter-status",
        subscription="status-writer",
        max_messages_per_execution=1,
    )

    processed = job_runner.run_once(cfg)

    assert processed is True
    assert client.subscription_calls == [("aidocwriter-status", "status-writer")]
    assert receiver.completed == ["m1"]


def test_run_once_raises_on_handler_error(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _FakeMessage({"job_id": "j3"})
    receiver = _FakeReceiver([message])
    client = _FakeClient(receiver)

    monkeypatch.setattr(job_runner.service_bus, "ensure_ready", lambda: None)
    monkeypatch.setattr(job_runner.service_bus, "get_client", lambda: client)
    monkeypatch.setattr(job_runner, "AutoLockRenewer", None)
    monkeypatch.setattr(
        job_runner,
        "STAGE_HANDLERS",
        {"plan": lambda data: (_ for _ in ()).throw(RuntimeError("boom"))},
    )

    cfg = job_runner.WorkerConfig(
        stage="plan",
        kind="queue",
        queue="docwriter-plan",
        topic=None,
        subscription=None,
        max_messages_per_execution=1,
    )

    with pytest.raises(RuntimeError, match="boom"):
        job_runner.run_once(cfg)
    assert receiver.completed == []
    assert receiver.abandoned == ["m1"]
