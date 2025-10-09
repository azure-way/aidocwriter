from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from docwriter.config import get_settings, Settings
from docwriter.storage import BlobStore


@lru_cache()
def get_cached_settings() -> Settings:
    return get_settings()


def blob_store_dependency() -> Iterator[BlobStore]:
    store = BlobStore()
    try:
        yield store
    finally:
        pass
