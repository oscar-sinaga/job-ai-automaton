"""Milestone 0 acceptance test.

Uses ASGI transport rather than a live server, so no port binding is needed
(docs/12 §2). The database may be absent -- ``/health`` must still return 200.
"""

from __future__ import annotations

import httpx
import pytest

from oscar_api.main import app


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    # Reports database state without failing on it -- see docs/05 §2.
    assert body["db"] in {"ok", "unavailable"}


async def test_openapi_schema_is_served(client: httpx.AsyncClient) -> None:
    """The extension and web client are generated against this schema."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
