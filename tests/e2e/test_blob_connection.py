from __future__ import annotations

import os
import uuid
import pytest

from docwriter.storage import BlobStore


required_envs = ["AZURE_STORAGE_CONNECTION_STRING"]


def _env_ready() -> bool:
    return all(os.getenv(k) for k in required_envs)


pytestmark = pytest.mark.skipif(not _env_ready(), reason="Blob E2E requires AZURE_STORAGE_CONNECTION_STRING")


@pytest.mark.e2e
def test_blob_connectivity_roundtrip():
    store = BlobStore()
    blob_path = f"tests/blob_connectivity/{uuid.uuid4()}.txt"
    payload = "DocWriter blob connectivity check"
    store.put_text(blob_path, payload)
    fetched = store.get_text(blob_path)
    assert fetched == payload
