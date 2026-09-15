"""Shared dependencies: the write-endpoint access key."""
from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import get_settings


def require_key(x_access_key: str | None = Header(default=None, alias="X-Access-Key")) -> str:
    settings = get_settings()
    expected = settings.access_key or ""
    if not expected:  # no key configured -> open (documented in docs/API.md)
        return "open"
    if x_access_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Access-Key")
    return "ok"


def check_key(key: str | None) -> bool:
    expected = get_settings().access_key or ""
    return (not expected) or key == expected
