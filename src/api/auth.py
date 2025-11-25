from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

import requests
from fastapi import HTTPException, status
from jose import jwt

from docwriter.config import get_settings


class AuthError(Exception):
    pass


@lru_cache()
def _get_jwks() -> Dict[str, Any]:
    settings = get_settings()
    issuer = settings.auth0_issuer_base_url
    if not issuer:
        raise AuthError("AUTH0_ISSUER_BASE_URL is not configured")
    url = issuer.rstrip("/") + "/.well-known/jwks.json"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


def verify_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    issuer = settings.auth0_issuer_base_url
    audience = settings.auth0_audience
    if not issuer or not audience:
        raise AuthError("Auth0 issuer/audience not configured")
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:  # pragma: no cover
        raise AuthError("Invalid token header") from exc
    jwks = _get_jwks()
    key = None
    for candidate in jwks.get("keys", []):
        if candidate.get("kid") == header.get("kid"):
            key = candidate
            break
    if key is None:
        raise AuthError("Unable to find matching JWKS key")
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer.rstrip("/"),
        )
    except Exception as exc:  # pragma: no cover
        raise AuthError("Token validation failed") from exc
    return payload


def require_user_id(token: str) -> str:
    payload = verify_token(token)
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise AuthError("Token missing subject")
    return user_id


def handle_auth_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(exc) or "Invalid token",
    )
