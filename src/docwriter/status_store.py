from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from .config import get_settings

_lock = threading.Lock()
_store: Optional["StatusTableStore"] = None


def _coerce_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return json.dumps(value)
    except Exception:
        return str(value)


class StatusTableStore:
    def __init__(self, connection_string: str, table_name: str) -> None:
        self._service = TableServiceClient.from_connection_string(connection_string)
        self._table = self._service.get_table_client(table_name)
        try:
            self._table.create_table()
        except ResourceExistsError:
            pass

    def record(self, payload: Dict[str, Any]) -> None:
        job_id = payload.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            return
        entity: Dict[str, Any] = {
            "PartitionKey": job_id,
            "RowKey": "latest",
            "job_id": job_id,
        }
        for key, value in payload.items():
            if key in {"PartitionKey", "RowKey"}:
                continue
            entity[key] = _coerce_value(value)
        entity["updated"] = _coerce_value(payload.get("ts"))
        self._table.upsert_entity(entity=entity, mode="replace")

    def latest(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            entity = self._table.get_entity(partition_key=job_id, row_key="latest")
        except ResourceNotFoundError:
            return None
        result: Dict[str, Any] = {}
        for key, value in dict(entity).items():
            if key in {"PartitionKey", "RowKey", "Timestamp"} or key.startswith("odata."):
                continue
            if key == "updated" and isinstance(value, str):
                result["ts"] = value
                continue
            result[key] = value
        if "job_id" not in result:
            result["job_id"] = job_id
        return result


def get_status_table_store() -> StatusTableStore:
    global _store
    with _lock:
        if _store is not None:
            return _store
        settings = get_settings()
        connection = settings.blob_connection_string
        if not connection:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for status table access")
        _store = StatusTableStore(connection, settings.status_table_name)
        return _store
