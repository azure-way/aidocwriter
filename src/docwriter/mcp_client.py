from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests

from .config import get_settings


class McpClient:
    def __init__(self):
        self.settings = get_settings()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def _get_token(self) -> Optional[str]:
        if not self.settings.mcp_token_url:
            return self.settings.mcp_access_token
        now = time.time()
        if self._token and now < self._token_expiry:
            return self._token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.settings.mcp_client_id,
            "client_secret": self.settings.mcp_client_secret,
        }
        if self.settings.mcp_audience:
            data["audience"] = self.settings.mcp_audience
        resp = requests.post(self.settings.mcp_token_url, data=data, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            return None
        expires_in = float(payload.get("expires_in", 300))
        self._token = token
        self._token_expiry = now + max(60.0, expires_in - 30)
        return token

    def _headers(self, token_override: Optional[str] = None) -> Dict[str, str]:
        token = token_override or self._get_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_company_profile(
        self,
        *,
        base_url: str | None = None,
        resource_path: str | None = None,
        token: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        resolved_base = base_url or self.settings.mcp_base_url
        resolved_resource = resource_path or self.settings.mcp_resource_company_profile
        if not resolved_base or not resolved_resource:
            return None
        url = f"{resolved_base.rstrip('/')}/{resolved_resource.lstrip('/')}"
        resp = requests.get(url, headers=self._headers(token), timeout=20)
        if resp.status_code >= 400:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None

    def query_company_profile(
        self,
        query: str,
        *,
        base_url: str | None = None,
        tool_path: str | None = None,
        token: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        resolved_base = base_url or self.settings.mcp_base_url
        resolved_tool = tool_path or self.settings.mcp_tool_company_query
        if not resolved_base or not resolved_tool:
            return None
        url = f"{resolved_base.rstrip('/')}/{resolved_tool.lstrip('/')}"
        resp = requests.post(url, headers=self._headers(token), data=json.dumps({"query": query}), timeout=20)
        if resp.status_code >= 400:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None

    def check_health(self, base_url: str, token: str | None = None) -> bool:
        if not base_url:
            return False
        for path in ("healthz", "health"):
            url = f"{base_url.rstrip('/')}/{path}"
            try:
                resp = requests.get(url, headers=self._headers(token), timeout=10)
                if resp.status_code < 400:
                    return True
            except Exception:
                continue
        return False

    def list_resources(self, base_url: str, token: str | None = None) -> Optional[Dict[str, Any]]:
        if not base_url:
            return None
        url = f"{base_url.rstrip('/')}/resources"
        resp = requests.get(url, headers=self._headers(token), timeout=15)
        if resp.status_code >= 400:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None

    def list_tools(self, base_url: str, token: str | None = None) -> Optional[Dict[str, Any]]:
        if not base_url:
            return None
        url = f"{base_url.rstrip('/')}/tools"
        resp = requests.get(url, headers=self._headers(token), timeout=15)
        if resp.status_code >= 400:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None
