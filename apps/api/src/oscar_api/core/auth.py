"""API key auth (docs/03_SYSTEM_ARCHITECTURE.md §4, docs/11_SECURITY_PRIVACY.md §3).

Single static shared secret compared in constant time. This is a network guard
against "anything else on the network can write to this API" -- not a user
identity system (ADR-002). It becomes inadequate the moment the API is exposed
publicly (see ADR-019 / OPEN-6).
"""

from __future__ import annotations

import secrets

from fastapi import Header

from oscar_api.config import get_settings
from oscar_api.core.errors import UnauthorizedError


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_key:
        # Fails closed rather than open: an unconfigured key must never be
        # treated as "auth disabled" (docs/14 §3).
        raise UnauthorizedError("OSCAR_API_KEY is not configured on the server")
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise UnauthorizedError("Missing or invalid X-API-Key")
