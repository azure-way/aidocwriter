from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from .config import get_settings

_lock = threading.Lock()
_store: Optional["DocumentIndexStore"] = None


def _coerce_value(value: Any) -> Any:
    if value is None:
        return value
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        return str(value)
    except Exception:
        return repr(value)


class DocumentIndexStore:
    def __init__(self, connection_string: str, table_name: str) -> None:
        self._service = TableServiceClient.from_connection_string(connection_string)
        self._table = self._service.get_table_client(table_name)
        try:
            self._table.create_table()
        except ResourceExistsError:
            pass

    def upsert(self, user_id: str, job_id: str, **fields: Any) -> None:
        if not user_id or not job_id:
            return
        entity: Dict[str, Any]
        try:
            existing = self._table.get_entity(partition_key=user_id, row_key=job_id)
            entity = {k: v for k, v in existing.items() if not k.startswith("odata.")}
        except ResourceNotFoundError:
            entity = {}
        entity.update(
            {
                "PartitionKey": user_id,
                "RowKey": job_id,
                "user_id": user_id,
                "job_id": job_id,
            }
        )
        timestamp = fields.get("updated")
        if timestamp is None:
            timestamp = time.time()
        entity["updated"] = float(timestamp)
        for key, value in fields.items():
            if value is None:
                continue
            entity[key] = _coerce_value(value)
        self._table.upsert_entity(entity=entity, mode="replace")

    def list(self, user_id: str) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        filter_expr = f"PartitionKey eq '{user_id}'"
        entities = list(self._table.query_entities(query_filter=filter_expr))
        docs = [self._convert(entity) for entity in entities]
        return sorted(docs, key=lambda item: item.get("updated") or 0, reverse=True)

    def get(self, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            entity = self._table.get_entity(partition_key=user_id, row_key=job_id)
        except ResourceNotFoundError:
            return None
        return self._convert(entity)

    @staticmethod
    def _convert(entity: Dict[str, Any]) -> Dict[str, Any]:
        doc: Dict[str, Any] = {}
        for key, value in dict(entity).items():
            if key in {"PartitionKey", "RowKey", "Timestamp"} or key.startswith("odata."):
                continue
            if key == "updated":
                try:
                    doc[key] = float(value)
                except (TypeError, ValueError):
                    doc[key] = None
                continue
            doc[key] = value
        return doc


def get_document_index_store() -> DocumentIndexStore:
    global _store
    with _lock:
        if _store is not None:
            return _store
        settings = get_settings()
        connection = settings.blob_connection_string
        if not connection:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for document index access")
        _store = DocumentIndexStore(connection, settings.documents_table_name)
        return _store
