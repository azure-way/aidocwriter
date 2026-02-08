from __future__ import annotations

from typing import Any, Dict, Optional

from .company_profile_store import get_company_profile_store
from .mcp_client import McpClient


def _merge_profile(user_profile: Dict[str, Any], mcp_profile: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(mcp_profile)
    for key, value in user_profile.items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
    return merged


def load_company_profile(user_id: str, mcp_token: Optional[str] = None) -> tuple[Dict[str, Any], Optional[str]]:
    user_profile: Dict[str, Any] = {}
    mcp_profile: Dict[str, Any] = {}
    warning: Optional[str] = None
    mcp_config: Dict[str, Any] = {}
    try:
        store = get_company_profile_store()
        stored = store.get(user_id) or {}
        user_profile = stored.get("profile") or {}
        mcp_config = stored.get("mcp_config") or {}
    except Exception:
        user_profile = {}
    try:
        mcp_profile = McpClient().get_company_profile(
            base_url=mcp_config.get("base_url"),
            resource_path=mcp_config.get("resource_path"),
            token=mcp_token,
        ) or {}
    except Exception:
        mcp_profile = {}
        warning = "Company MCP data unavailable"
    merged = _merge_profile(user_profile, mcp_profile)
    return merged, warning


def profile_context_text(profile: Dict[str, Any]) -> str:
    if not profile:
        return ""
    parts = ["Company Profile Context:"]
    for key in [
        "company_name",
        "overview",
        "capabilities",
        "industries",
        "certifications",
        "locations",
        "references",
    ]:
        if key not in profile:
            continue
        parts.append(f"- {key}: {profile.get(key)}")
    return "\n".join(parts)
