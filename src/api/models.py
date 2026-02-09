from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class JobCreateRequest(BaseModel):
    title: str = Field(..., description="Document title")
    audience: str = Field(..., description="Target audience")
    cycles: int = Field(1, ge=1, description="Maximum review/rewrite cycles")


class JobCreateResponse(BaseModel):
    job_id: str


class ResumeRequest(BaseModel):
    answers: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured intake answers; if omitted existing Blob content is reused.",
    )

    @field_validator("answers", mode="before")
    def _empty_dict_becomes_none(cls, value):  # type: ignore[override]
        if value == {}:
            return None
        return value


class ResumeResponse(BaseModel):
    job_id: str
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"


class StatusResponse(BaseModel):
    job_id: str
    stage: str
    artifact: Optional[str] = None
    message: Optional[str] = None
    cycle: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class BlobDownloadResponse(BaseModel):
    path: str
    content_type: str


class StatusEventEntry(BaseModel):
    stage: str
    message: Optional[str] = None
    artifact: Optional[str] = None
    ts: Optional[float] = None
    cycle: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class StatusTimelineResponse(BaseModel):
    job_id: str
    events: List[StatusEventEntry]
    meta: Optional[Dict[str, Any]] = None


class IntakeQuestionsRequest(BaseModel):
    title: str = Field(..., description="Document title to scope intake questions")


class IntakeQuestion(BaseModel):
    id: str
    q: str
    sample: str = ""


class IntakeQuestionsResponse(BaseModel):
    title: str
    questions: List[IntakeQuestion]


class DocumentListEntry(BaseModel):
    job_id: str
    title: Optional[str] = None
    audience: Optional[str] = None
    stage: Optional[str] = None
    message: Optional[str] = None
    artifact: Optional[str] = None
    updated: Optional[float] = None
    cycles_requested: Optional[int] = None
    cycles_completed: Optional[int] = None
    has_error: Optional[bool] = None
    last_error: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentListEntry]


class CompanyReference(BaseModel):
    title: str
    summary: str
    outcome: Optional[str] = None
    year: Optional[str] = None


class CompanyProfile(BaseModel):
    company_name: str
    overview: str
    capabilities: List[str]
    industries: List[str]
    certifications: List[str]
    locations: List[str]
    references: List[CompanyReference]


class CompanyProfileRequest(BaseModel):
    profile: CompanyProfile
    mcp_config: Optional[Dict[str, str]] = None


class CompanyProfileSource(BaseModel):
    filename: str
    blob_path: str


class CompanyProfileResponse(BaseModel):
    profile: CompanyProfile
    sources: List[CompanyProfileSource]
    updated: Optional[float] = None
    mcp_config: Optional[Dict[str, str]] = None


class McpDiscoverRequest(BaseModel):
    base_url: str


class McpResourceEntry(BaseModel):
    name: str
    path: str
    description: Optional[str] = None


class McpToolEntry(BaseModel):
    name: str
    path: str
    description: Optional[str] = None


class McpDiscoverResponse(BaseModel):
    resources: List[McpResourceEntry]
    tools: List[McpToolEntry]
