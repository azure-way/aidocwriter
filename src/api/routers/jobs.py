from __future__ import annotations

import json
import tempfile
from fastapi import APIRouter, Depends, HTTPException, status
from azure.core.exceptions import ResourceNotFoundError

from docwriter.queue import Job, send_job, send_resume
from docwriter.storage import BlobStore

from ..deps import blob_store_dependency
from ..models import (
    JobCreateRequest,
    JobCreateResponse,
    ResumeRequest,
    ResumeResponse,
    StatusResponse,
)
from ..status_store import status_store

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreateRequest) -> JobCreateResponse:
    tmp_path = tempfile.NamedTemporaryFile(prefix="docwriter_", suffix=".md", delete=False)
    tmp_path.close()
    job = Job(
        title=payload.title,
        audience=payload.audience,
        out=tmp_path.name,
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
    latest = status_store.latest(job_id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found in status cache")
    return StatusResponse(
        job_id=job_id,
        stage=str(latest.get("stage", "UNKNOWN")),
        artifact=latest.get("artifact"),
        message=latest.get("message"),
        cycle=latest.get("cycle"),
    )
