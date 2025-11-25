from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from fastapi import Header, HTTPException, status

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


def user_id_dependency(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id header required")
    return x_user_id
