from __future__ import annotations

from dataclasses import dataclass
import posixpath

try:
    from azure.storage.blob import BlobServiceClient  # type: ignore
except Exception:  # pragma: no cover
    BlobServiceClient = None  # type: ignore

from .config import get_settings


@dataclass(frozen=True)
class BlobPath:
    container: str
    blob: str


@dataclass(frozen=True)
class JobStoragePaths:
    user_id: str
    job_id: str

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("user_id is required for JobStoragePaths")
        if not self.job_id:
            raise ValueError("job_id is required for JobStoragePaths")

    @property
    def root(self) -> str:
        return f"jobs/{self._sanitize_segment(self.user_id)}/{self._sanitize_segment(self.job_id)}"

    def draft(self) -> str:
        return self._join("draft.md")

    def final(self, suffix: str = "md") -> str:
        suffix = suffix.lstrip(".")
        return self._join(f"final.{suffix}")

    def plan(self) -> str:
        return self._join("plan.json")

    def intake(self, relative: str) -> str:
        return self._join("intake", relative)

    def images(self, relative: str) -> str:
        return self._join("images", relative)

    def diagrams(self, relative: str) -> str:
        return self._join("diagrams", relative)

    def metrics(self, relative: str) -> str:
        return self._join("metrics", relative)

    def cycle(self, cycle_idx: int, relative: str) -> str:
        if cycle_idx < 0:
            raise ValueError("cycle_idx must be non-negative")
        return self._join(f"cycle_{cycle_idx}", relative)

    def relative(self, relative: str) -> str:
        return self._join(relative)

    def _join(self, *segments: str) -> str:
        normalized = [self._normalize_relative(seg) for seg in segments if seg]
        if not normalized:
            return self.root
        return f"{self.root}/{'/'.join(normalized)}"

    @staticmethod
    def _sanitize_segment(segment: str) -> str:
        segment = (segment or "").strip().strip("/")
        if not segment:
            raise ValueError("Segment cannot be empty")
        if any(part in {"..", "."} for part in segment.split("/")):
            raise ValueError("Segment cannot contain relative path navigation")
        return segment

    @staticmethod
    def _normalize_relative(relative: str) -> str:
        relative = (relative or "").strip()
        if not relative:
            raise ValueError("Relative path segment cannot be empty")
        cleaned = posixpath.normpath(relative.strip("/"))
        if cleaned in {"", "."}:
            raise ValueError("Relative path resolves to empty")
        if cleaned.startswith("../") or cleaned == "..":
            raise ValueError("Relative path cannot ascend from job root")
        return cleaned


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

    def allocate_document_blob(self, job_id: str, user_id: str) -> str:
        return JobStoragePaths(user_id=user_id, job_id=job_id).draft()

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
