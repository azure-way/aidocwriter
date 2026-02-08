from __future__ import annotations

import time
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Header

from docwriter.company_profile_store import get_company_profile_store
from docwriter.profile_extract import extract_profile_text
from docwriter.agents.core_company_profile import CoreCompanyProfileAgent
from docwriter.storage import BlobStore
from docwriter.mcp_client import McpClient

from ..deps import current_user_dependency, blob_store_dependency
from ..models import CompanyProfileRequest, CompanyProfileResponse, CompanyProfileSource, CompanyProfile

router = APIRouter(prefix="/profile", tags=["profile"])

try:  # pragma: no cover - optional dependency for multipart uploads
    import python_multipart  # type: ignore  # noqa: F401

    _multipart_available = True
except Exception:  # pragma: no cover
    _multipart_available = False


def _sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "").strip("._")
    return cleaned or "upload"


def _default_profile() -> CompanyProfile:
    return CompanyProfile(
        company_name="",
        overview="",
        capabilities=[],
        industries=[],
        certifications=[],
        locations=[],
        references=[],
    )


def _merge_profile(existing: dict, incoming: dict) -> dict:
    merged = dict(incoming)
    for key, value in existing.items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
    return merged


@router.get("/company", response_model=CompanyProfileResponse)
def get_company_profile(user_id: str = Depends(current_user_dependency)) -> CompanyProfileResponse:
    store = get_company_profile_store()
    record = store.get(user_id)
    if not record:
        return CompanyProfileResponse(profile=_default_profile(), sources=[], updated=None, mcp_config={})
    profile = record.get("profile") or {}
    sources = record.get("sources") or []
    mcp_config = record.get("mcp_config") or {}
    return CompanyProfileResponse(
        profile=CompanyProfile(**profile) if profile else _default_profile(),
        sources=[CompanyProfileSource(**item) for item in sources],
        updated=record.get("updated"),
        mcp_config=mcp_config,
    )


@router.put("/company", response_model=CompanyProfileResponse)
def update_company_profile(
    payload: CompanyProfileRequest,
    authorization: str = Header(..., alias="Authorization"),
    user_id: str = Depends(current_user_dependency),
) -> CompanyProfileResponse:
    store = get_company_profile_store()
    existing = store.get(user_id) or {}
    sources = existing.get("sources") or []
    mcp_config = payload.mcp_config or existing.get("mcp_config") or {}
    if mcp_config:
        base_url = mcp_config.get("base_url", "").strip()
        resource_path = mcp_config.get("resource_path", "").strip()
        tool_path = mcp_config.get("tool_path", "").strip()
        if not base_url.startswith("http"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MCP base_url is required")
        if not resource_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MCP resource_path is required")
        if not tool_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MCP tool_path is required")
        mcp_config = {
            "base_url": base_url,
            "resource_path": resource_path,
            "tool_path": tool_path,
        }
        scheme, _, token = authorization.partition(" ")
        bearer = token if scheme.lower() == "bearer" and token else None
        if not McpClient().check_health(base_url, token=bearer):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MCP health check failed")
    store.upsert(user_id, profile=payload.profile.model_dump(), sources=sources, mcp_config=mcp_config)
    return CompanyProfileResponse(
        profile=payload.profile,
        sources=[CompanyProfileSource(**item) for item in sources],
        updated=time.time(),
        mcp_config=mcp_config,
    )


if _multipart_available:
    @router.post("/company/upload", response_model=CompanyProfileResponse, status_code=status.HTTP_202_ACCEPTED)
    def upload_company_profile(
        file: UploadFile = File(...),
        user_id: str = Depends(current_user_dependency),
        blob_store: BlobStore = Depends(blob_store_dependency),
    ) -> CompanyProfileResponse:
        filename = _sanitize_filename(file.filename or "company-profile")
        extension = filename.split(".")[-1].lower()
        if extension not in {"pdf", "docx", "pptx"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported profile file type")
        data = file.file.read()
        blob_path = f"company-profiles/{user_id}/{int(time.time())}-{filename}"
        blob_store.put_bytes(blob=blob_path, data_bytes=data)
        try:
            text = extract_profile_text(data, extension)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        agent = CoreCompanyProfileAgent()
        extracted = agent.extract(text, metadata={"filename": filename})
        profile_store = get_company_profile_store()
        existing = profile_store.get(user_id) or {}
        existing_profile = existing.get("profile") or {}
        mcp_config = existing.get("mcp_config") or {}
        merged_profile = _merge_profile(existing_profile, extracted)
        sources = existing.get("sources") or []
        sources.append({"filename": filename, "blob_path": blob_path})
        profile_store.upsert(user_id, profile=merged_profile, sources=sources, mcp_config=mcp_config)
        return CompanyProfileResponse(
            profile=CompanyProfile(**merged_profile),
            sources=[CompanyProfileSource(**item) for item in sources],
            updated=time.time(),
            mcp_config=mcp_config,
        )
