from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from fastapi import Header, HTTPException, status

from docwriter.config import get_settings, Settings
from docwriter.storage import BlobStore
from .auth import require_user_id, handle_auth_error


@lru_cache()
def get_cached_settings() -> Settings:
    return get_settings()


def blob_store_dependency() -> Iterator[BlobStore]:
    store = BlobStore()
    try:
        yield store
    finally:
        pass


def current_user_dependency(authorization: str = Header(..., alias="Authorization")) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        return require_user_id(token)
    except Exception as exc:  # pragma: no cover
        raise handle_auth_error(exc)
