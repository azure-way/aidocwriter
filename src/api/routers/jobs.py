from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, status, Response
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from docwriter.queue import Job, send_job, send_resume
from docwriter.storage import BlobStore
from docwriter.status_store import get_status_table_store

from ..deps import blob_store_dependency
from ..models import (
    JobCreateRequest,
    JobCreateResponse,
    ResumeRequest,
    ResumeResponse,
    StatusResponse,
    BlobDownloadResponse,
)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreateRequest) -> JobCreateResponse:
    job = Job(
        title=payload.title,
        audience=payload.audience,
        cycles=payload.cycles,
    )
    job_id = send_job(job)
    return JobCreateResponse(job_id=job_id)


@router.post("/{job_id}/resume", response_model=ResumeResponse, status_code=status.HTTP_202_ACCEPTED)
def resume_job(
    job_id: str,
    payload: ResumeRequest,
    store: BlobStore = Depends(blob_store_dependency),
) -> ResumeResponse:
    blob_path = f"jobs/{job_id}/intake/answers.json"
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

    send_resume(job_id)
    return ResumeResponse(job_id=job_id, message="Resume signal sent")


@router.get("/{job_id}/status", response_model=StatusResponse)
def job_status(job_id: str) -> StatusResponse:
    try:
        status_store = get_status_table_store()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
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


@router.get("/artifacts")
def download_artifact(
    path: str,
    store: BlobStore = Depends(blob_store_dependency),
) -> Response:
    if not path or path.startswith("/") or ".." in path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid blob path")
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
