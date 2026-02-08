from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from .config import get_settings

_lock = threading.Lock()
_store: Optional["CompanyProfileStore"] = None


def _coerce_value(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        return str(value)
    except Exception:
        return repr(value)


class CompanyProfileStore:
    def __init__(self, connection_string: str, table_name: str) -> None:
        self._service = TableServiceClient.from_connection_string(connection_string)
        self._table = self._service.get_table_client(table_name)
        try:
            self._table.create_table()
        except ResourceExistsError:
            pass

    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not user_id:
            return None
        try:
            entity = self._table.get_entity(partition_key=user_id, row_key="company")
        except ResourceNotFoundError:
            return None
        profile_json = entity.get("profile_json")
        try:
            profile = json.loads(profile_json) if profile_json else {}
        except json.JSONDecodeError:
            profile = {}
        sources_json = entity.get("sources_json")
        try:
            sources = json.loads(sources_json) if sources_json else []
        except json.JSONDecodeError:
            sources = []
        mcp_json = entity.get("mcp_json")
        try:
            mcp_config = json.loads(mcp_json) if mcp_json else {}
        except json.JSONDecodeError:
            mcp_config = {}
        return {
            "profile": profile,
            "sources": sources,
            "updated": entity.get("updated"),
            "mcp_config": mcp_config,
        }

    def upsert(
        self,
        user_id: str,
        profile: Dict[str, Any],
        sources: list[dict[str, Any]] | None = None,
        mcp_config: Dict[str, Any] | None = None,
    ) -> None:
        if not user_id:
            return
        entity: Dict[str, Any]
        try:
            existing = self._table.get_entity(partition_key=user_id, row_key="company")
            entity = {k: v for k, v in existing.items() if not k.startswith("odata.")}
        except ResourceNotFoundError:
            entity = {}
        entity.update(
            {
                "PartitionKey": user_id,
                "RowKey": "company",
                "user_id": user_id,
                "updated": float(time.time()),
                "profile_json": json.dumps(profile),
                "sources_json": json.dumps(sources or []),
                "mcp_json": json.dumps(mcp_config or {}),
            }
        )
        for key, value in list(entity.items()):
            entity[key] = _coerce_value(value)
        self._table.upsert_entity(entity=entity, mode="replace")


def get_company_profile_store() -> CompanyProfileStore:
    global _store
    with _lock:
        if _store is not None:
            return _store
        settings = get_settings()
        connection = settings.blob_connection_string
        if not connection:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for company profile access")
        _store = CompanyProfileStore(connection, settings.company_profiles_table_name)
        return _store
