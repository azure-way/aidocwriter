from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from .config import get_settings
from .document_index import get_document_index_store

_lock = threading.Lock()
_store: Optional["StatusTableStore"] = None


def _coerce_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return json.dumps(value)
    except Exception:
        return str(value)


def _history_row_key(ts: float, stage: Optional[str]) -> str:
    stage_label = (stage or "UNKNOWN").replace(" ", "_")
    return f"{int(ts * 1_000_000):020d}_{stage_label}"


def _coerce_int_safe(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
        timestamp = payload.get("ts")
        try:
            ts = float(timestamp)
        except Exception:
            ts = time.time()
        entity: Dict[str, Any] = {
            "PartitionKey": job_id,
            "RowKey": "latest",
            "job_id": job_id,
        }
        for key, value in payload.items():
            if key in {"PartitionKey", "RowKey"}:
                continue
            entity[key] = _coerce_value(value)
        entity["updated"] = _coerce_value(ts)
        self._table.upsert_entity(entity=entity, mode="replace")

        history_entity = dict(entity)
        history_entity["RowKey"] = _history_row_key(ts, payload.get("stage"))
        history_entity["is_latest"] = False
        self._table.upsert_entity(entity=history_entity, mode="replace")

        user_id = payload.get("user_id")
        if isinstance(user_id, str) and user_id:
            try:
                index_store = get_document_index_store()
                details_payload = payload.get("details")
                expected_cycles = None
                cycles_completed = None
                if isinstance(details_payload, dict):
                    expected_cycles = details_payload.get("expected_cycles") or details_payload.get("cycles")
                    cycles_completed = details_payload.get("cycles_completed")
                if expected_cycles is None:
                    expected_cycles = payload.get("cycles")
                stage_value = str(payload.get("stage", ""))
                stage_upper = stage_value.upper()
                has_error = stage_upper.endswith("_FAILED")
                index_store.upsert(
                    user_id,
                    job_id,
                    stage=stage_value,
                    message=payload.get("message"),
                    artifact=payload.get("artifact"),
                    updated=ts,
                    cycles_requested=_coerce_int_safe(expected_cycles),
                    cycles_completed=_coerce_int_safe(cycles_completed),
                    has_error=has_error,
                    last_error=payload.get("message") if has_error else None,
                )
            except Exception:
                pass

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

    def timeline(self, job_id: str) -> List[Dict[str, Any]]:
        filter_expr = f"PartitionKey eq '{job_id}' and RowKey ne 'latest'"
        entities = list(self._table.query_entities(query_filter=filter_expr))
        events: List[Dict[str, Any]] = []
        for entity in sorted(entities, key=lambda e: e["RowKey"]):
            event: Dict[str, Any] = {"job_id": job_id}
            for key, value in dict(entity).items():
                if key in {"PartitionKey", "RowKey", "Timestamp"} or key.startswith("odata."):
                    continue
                if key == "updated":
                    event["ts"] = value
                    continue
                event[key] = value
            if "ts" not in event:
                event["ts"] = entity.get("RowKey")
            events.append(event)
        return events


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
