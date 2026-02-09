from __future__ import annotations

import threading
from typing import List, Optional

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableServiceClient

from .config import get_settings

_lock = threading.Lock()
_store: Optional["FeatureFlagsStore"] = None


class FeatureFlagsStore:
    def __init__(self, connection_string: str, table_name: str) -> None:
        self._service = TableServiceClient.from_connection_string(connection_string)
        self._table = self._service.get_table_client(table_name)
        try:
            self._table.create_table()
        except ResourceExistsError:
            pass

    def is_allowed(self, feature_key: str, user_id: str) -> bool:
        if not feature_key or not user_id:
            return False
        try:
            self._table.get_entity(partition_key=feature_key, row_key=user_id)
            return True
        except ResourceNotFoundError:
            return False

    def list_features(self, user_id: str) -> List[str]:
        if not user_id:
            return []
        query = f"RowKey eq '{user_id}'"
        entities = list(self._table.query_entities(query_filter=query))
        features: List[str] = []
        for entity in entities:
            key = entity.get("PartitionKey")
            if isinstance(key, str) and key.strip():
                features.append(key)
        return sorted(set(features))


def get_feature_flags_store() -> FeatureFlagsStore:
    global _store
    with _lock:
        if _store is not None:
            return _store
        settings = get_settings()
        connection = settings.blob_connection_string
        if not connection:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for feature flags access")
        _store = FeatureFlagsStore(connection, settings.feature_flags_table_name)
        return _store
