from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, Depends, HTTPException, status, Response
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from docwriter.queue import Job, send_job, send_resume
from docwriter.storage import BlobStore, JobStoragePaths
from docwriter.status_store import get_status_table_store
from docwriter.document_index import get_document_index_store

from ..deps import blob_store_dependency, current_user_dependency
from ..models import (
    JobCreateRequest,
    JobCreateResponse,
    ResumeRequest,
    ResumeResponse,
    StatusResponse,
    BlobDownloadResponse,
    StatusTimelineResponse,
    StatusEventEntry,
    DocumentListEntry,
    DocumentListResponse,
)
router = APIRouter(prefix="/jobs", tags=["jobs"])

SUMMARY_STAGE_ORDER = [
    "ENQUEUED",
    "INTAKE_READY",
    "INTAKE_RESUME",
    "PLAN",
    "WRITE",
    "REVIEW",
    "VERIFY",
    "REWRITE",
    "DIAGRAM",
    "FINALIZE",
]


def _parse_stage_message(message: str) -> dict[str, object]:
    if not isinstance(message, str) or not message.strip():
        return {}
    parts = [part.strip() for part in message.split(" | ") if part.strip()]
    if not parts:
        return {}
    key_map = {
        "stage_completed": "stage_label",
        "stage_document": "document",
        "stage_time": "duration",
        "stage_tokens": "tokens_display",
        "stage_model": "model",
        "stage_notes": "notes",
    }
    data: dict[str, object] = {}
    for part in parts:
        if ": " not in part:
            continue
        key, value = part.split(": ", 1)
        normalized_key = key.strip().lower().replace(" ", "_")
        mapped_key = key_map.get(normalized_key)
        if not mapped_key:
            continue
        clean_value = value.strip()
        if not clean_value:
            continue
        if mapped_key == "tokens_display":
            data[mapped_key] = clean_value
            numeric = re.sub(r"[^\d]", "", clean_value)
            if numeric.isdigit():
                try:
                    data["tokens"] = int(numeric)
                except ValueError:
                    pass
            continue
        data[mapped_key] = clean_value
    return data


@router.get("", response_model=DocumentListResponse)
def list_jobs(user_id: str = Depends(current_user_dependency)) -> DocumentListResponse:
    store = get_document_index_store()
    records = store.list(user_id)
    documents = [DocumentListEntry(**record) for record in records]
    return DocumentListResponse(documents=documents)


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreateRequest, user_id: str = Depends(current_user_dependency)) -> JobCreateResponse:
    job = Job(
        title=payload.title,
        audience=payload.audience,
        cycles=payload.cycles,
        user_id=user_id,
    )
    job_id = send_job(job)
    index_store = get_document_index_store()
    index_store.upsert(
        user_id,
        job_id,
        title=payload.title,
        audience=payload.audience,
        stage="ENQUEUED",
        message="Job submitted",
        updated=time.time(),
    )
    return JobCreateResponse(job_id=job_id)


@router.post("/{job_id}/resume", response_model=ResumeResponse, status_code=status.HTTP_202_ACCEPTED)
def resume_job(
    job_id: str,
    payload: ResumeRequest,
    store: BlobStore = Depends(blob_store_dependency),
    user_id: str = Depends(current_user_dependency),
) -> ResumeResponse:
    index_store = get_document_index_store()
    existing = index_store.get(user_id, job_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found for user")
    job_paths = JobStoragePaths(user_id=user_id, job_id=job_id)
    blob_path = job_paths.intake("answers.json")
    if payload.answers is not None:
        store.put_text(blob=blob_path, text=json.dumps(payload.answers, indent=2))
    else:
        try:
            store.get_text(blob_path)
        except ResourceNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No answers found. Provide 'answers' in the request body.",
            ) from exc

    index_store.upsert(
        user_id,
        job_id,
        stage="INTAKE_READY",
        message="Resume requested",
        updated=time.time(),
    )
    send_resume(job_id, user_id=user_id)
    return ResumeResponse(job_id=job_id, message="Resume signal sent")


@router.get("/{job_id}/status", response_model=StatusResponse)
def job_status(job_id: str, user_id: str = Depends(current_user_dependency)) -> StatusResponse:
    try:
        status_store = get_status_table_store()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    index_store = get_document_index_store()
    existing = index_store.get(user_id, job_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found for user")
    latest = status_store.latest(job_id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found in status cache")
    details = latest.get("details")
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {"raw": details}
    return StatusResponse(
        job_id=job_id,
        stage=str(latest.get("stage", "UNKNOWN")),
        artifact=latest.get("artifact"),
        message=latest.get("message"),
        cycle=latest.get("cycle"),
        details=details,
    )


@router.get("/{job_id}/timeline", response_model=StatusTimelineResponse)
def job_timeline(job_id: str, user_id: str = Depends(current_user_dependency)) -> StatusTimelineResponse:
    try:
        status_store = get_status_table_store()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    index_store = get_document_index_store()
    existing = index_store.get(user_id, job_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found for user")
    events_raw = status_store.timeline(job_id)
    events: list[StatusEventEntry] = []
    expected_cycles = 1
    for item in events_raw:
        details = item.get("details")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = {"raw": details}
        ts_raw = item.get("ts")
        try:
            ts_value = float(ts_raw)
        except (TypeError, ValueError):
            ts_value = None
        cycle_raw = item.get("cycle")
        try:
            cycle_value = int(cycle_raw) if cycle_raw is not None else None
        except (TypeError, ValueError):
            cycle_value = None
        parsed_message = _parse_stage_message(item.get("message"))
        details_dict: dict[str, object] = {}
        if isinstance(details, dict):
            details_dict.update(details)
        if parsed_message:
            existing = details_dict.get("parsed_message")
            if isinstance(existing, dict):
                existing.update(parsed_message)
            else:
                details_dict["parsed_message"] = parsed_message
        details_payload = details_dict if details_dict else None
        events.append(
            StatusEventEntry(
                stage=str(item.get("stage", "UNKNOWN")),
                message=item.get("message"),
                artifact=item.get("artifact"),
                ts=ts_value,
                cycle=cycle_value,
                details=details_payload,
            )
        )
        if isinstance(details, dict):
            expected = details.get("expected_cycles")
            if isinstance(expected, (int, float)):
                expected_cycles = max(expected_cycles, int(expected))
            elif isinstance(expected, str):
                try:
                    expected_cycles = max(expected_cycles, int(expected))
                except ValueError:
                    pass
        if cycle_value:
            expected_cycles = max(expected_cycles, cycle_value)
    meta = {
        "stage_order": SUMMARY_STAGE_ORDER,
        "expected_cycles": expected_cycles,
    }
    return StatusTimelineResponse(job_id=job_id, events=events, meta=meta)


@router.get("/artifacts")
def download_artifact(
    path: str,
    store: BlobStore = Depends(blob_store_dependency),
    user_id: str = Depends(current_user_dependency),
) -> Response:
    if not path or path.startswith("/") or ".." in path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blob path")
    parts = path.split("/")
    if len(parts) < 2 or parts[0] != "jobs":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed artifact path")
    job_id = parts[1]
    index_store = get_document_index_store()
    existing = index_store.get(user_id, job_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found for user")
    try:
        blob = store.container.get_blob_client(path)
        props = blob.get_blob_properties()
        data = blob.download_blob().readall()
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found") from exc
    except HttpResponseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Blob download failed") from exc
    content_type = props.content_settings.content_type or "application/octet-stream"
    headers = {"Content-Disposition": f'attachment; filename="{path.split("/")[-1]}"'}
    return Response(content=data, media_type=content_type, headers=headers)
