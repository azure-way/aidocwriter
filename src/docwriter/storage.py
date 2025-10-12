from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    from azure.storage.blob import BlobServiceClient  # type: ignore
except Exception:  # pragma: no cover
    BlobServiceClient = None  # type: ignore

from .config import get_settings


@dataclass
class BlobPath:
    container: str
    blob: str


class BlobStore:
    def __init__(self):
        self.settings = get_settings()
        if BlobServiceClient is None:
            raise RuntimeError(
                "azure-storage-blob not installed. Install with `pip install azure-storage-blob`."
            )
        if not self.settings.blob_connection_string:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")
        self.client = BlobServiceClient.from_connection_string(self.settings.blob_connection_string)
        self.container = self.client.get_container_client(self.settings.blob_container)
        try:
            self.container.create_container()
        except Exception:
            pass

    def allocate_document_blob(self, job_id: str) -> str:
        return f"jobs/{job_id}/draft.md"

    def put_text(self, blob: str, text: str) -> BlobPath:
        self.container.upload_blob(name=blob, data=text.encode("utf-8"), overwrite=True)
        return BlobPath(container=self.settings.blob_container, blob=blob)

    def put_bytes(self, blob: str, data_bytes: bytes) -> BlobPath:
        self.container.upload_blob(name=blob, data=data_bytes, overwrite=True)
        return BlobPath(container=self.settings.blob_container, blob=blob)

    def get_text(self, blob: str) -> str:
        data = self.container.download_blob(blob).readall()
        return data.decode("utf-8")

    def get_bytes(self, blob: str) -> bytes:
        return self.container.download_blob(blob).readall()
