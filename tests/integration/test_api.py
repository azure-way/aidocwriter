from __future__ import annotations

import json
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from azure.core.exceptions import ResourceNotFoundError

from api.main import app

class FakeStatusTableStore:
    def __init__(self) -> None:
        self._latest: Dict[str, Dict] = {}
        self._history: Dict[str, list[Dict]] = {}

    def record(self, payload: Dict) -> None:
        job_id = payload.get("job_id")
        if not job_id:
            return
        self._latest[job_id] = payload
        self._history.setdefault(job_id, []).append(payload.copy())

    def latest(self, job_id: str) -> Dict | None:
        return self._latest.get(job_id)

    def timeline(self, job_id: str) -> list[Dict]:
        return self._history.get(job_id, [])


@pytest.fixture(autouse=True)
def fake_status_table(monkeypatch):
    store = FakeStatusTableStore()
    monkeypatch.setattr("docwriter.status_store.get_status_table_store", lambda: store)
    yield store


@pytest.fixture
def client(monkeypatch):
    saved_jobs = {}

    def fake_send_job(job):
        job_id = f"job-{len(saved_jobs) + 1}"
        saved_jobs[job_id] = job
        return job_id

    def fake_send_resume(job_id):
        saved_jobs.setdefault(job_id, None)

    class FakeBlobStore:
        def __init__(self):
            self.storage: Dict[str, str] = {}

        def put_text(self, *, blob: str, text: str) -> None:
            self.storage[blob] = text

        def get_text(self, blob: str) -> str:
            try:
                return self.storage[blob]
            except KeyError as exc:
                raise ResourceNotFoundError("Blob not found") from exc

    fake_store = FakeBlobStore()

    class FakeInterviewer:
        def propose_questions(self, title: str):
            return [{"id": "audience", "q": f"Audience for {title}?", "sample": "Integration architects"}]

    monkeypatch.setattr("api.routers.jobs.send_job", fake_send_job)
    monkeypatch.setattr("api.routers.jobs.send_resume", fake_send_resume)
    monkeypatch.setattr("api.routers.jobs.BlobStore", lambda: fake_store)
    monkeypatch.setattr("api.routers.intake.InterviewerAgent", lambda: FakeInterviewer())

    return TestClient(app)


def test_create_job(client):
    resp = client.post(
        "/jobs",
        json={"title": "Doc", "audience": "Architects", "cycles": 2},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"].startswith("job-")


def test_resume_job_with_answers(client):
    job_id = client.post(
        "/jobs",
        json={"title": "Doc", "audience": "Architects"},
    ).json()["job_id"]

    answers = {"audience": "Architects"}
    resp = client.post(
        f"/jobs/{job_id}/resume",
        json={"answers": answers},
    )
    assert resp.status_code == 202
    payload = resp.json()
    assert payload["job_id"] == job_id
    assert payload["message"]


def test_resume_job_without_answers_requires_existing_blob(client):
    job_id = client.post(
        "/jobs",
        json={"title": "Doc", "audience": "Architects"},
    ).json()["job_id"]

    resp = client.post(f"/jobs/{job_id}/resume", json={})
    assert resp.status_code == 400


def test_intake_questions_endpoint(client):
    resp = client.post("/intake/questions", json={"title": "Async"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["questions"][0]["q"].startswith("Audience for Async")


def test_job_status_reflects_latest_event(client, fake_status_table):
    job_id = client.post(
        "/jobs",
        json={"title": "Doc", "audience": "Architects"},
    ).json()["job_id"]

    fake_status_table.record({"job_id": job_id, "stage": "PLAN", "cycle": 1})
    resp = client.get(f"/jobs/{job_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "PLAN"
    assert data["cycle"] == 1

    resp_missing = client.get("/jobs/unknown/status")
    assert resp_missing.status_code == 404


def test_job_timeline_returns_events(client, fake_status_table):
    job_id = client.post(
        "/jobs",
        json={"title": "Doc", "audience": "Architects"},
    ).json()["job_id"]

    fake_status_table.record({"job_id": job_id, "stage": "PLAN", "cycle": 1, "ts": 1.0})
    fake_status_table.record({"job_id": job_id, "stage": "WRITE_DONE", "cycle": None, "ts": 2.0})

    resp = client.get(f"/jobs/{job_id}/timeline")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["job_id"] == job_id
    assert len(payload["events"]) == 2
