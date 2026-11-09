"""Shared test fixtures.

Env vars are set before any `oscar_api` import so `get_settings()` (cached at
first call) picks up test values. Tests always run against a real Postgres --
never SQLite (docs/12_TEST_STRATEGY.md §2): the schema uses enums, JSONB, and
partial unique indexes that SQLite can't represent.

Each test runs inside a savepoint that is rolled back at teardown, so tests
never see each other's data even though `service.py` calls `session.commit()`
mid-request (the standard "join a session into an external transaction" recipe).
"""

from __future__ import annotations

import os

os.environ.setdefault("OSCAR_ENV", "test")
os.environ.setdefault("OSCAR_API_KEY", "test-local-key")
os.environ.setdefault("OSCAR_DATABASE_URL", "postgresql+psycopg://oscar:oscar@127.0.0.1:5432/oscar")

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from fakes import FakeLLMProvider, InMemoryStorage
from oscar_api.db import engine, get_session
from oscar_api.main import app
from oscar_api.modules.cv.deps import get_llm_provider, get_storage

_REPO_API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema() -> None:
    """Bring the test database to `head` once per test session."""
    cfg = Config(str(_REPO_API_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session bound to a connection whose outer transaction is always
    rolled back -- `session.commit()` inside application code only ends an
    inner SAVEPOINT, which is immediately restarted."""
    connection = engine.connect()
    outer_transaction = connection.begin()
    # SQLAlchemy 2 creates a new savepoint after each service commit/rollback.
    # A service rollback must not roll back the connection's outer transaction.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    """Queue responses with `fake_llm.queue({...})` before calling an endpoint
    that generates a CV -- no test ever calls a real model (docs/12 §2)."""
    return FakeLLMProvider()


@pytest.fixture
def fake_storage() -> InMemoryStorage:
    """Keeps CV-export tests independent of `var/storage/` on disk."""
    return InMemoryStorage()


@pytest_asyncio.fixture
async def client(
    db_session: Session, fake_llm: FakeLLMProvider, fake_storage: InMemoryStorage
) -> AsyncIterator[httpx.AsyncClient]:
    """An authenticated HTTP client wired to the test-isolated session and
    fake LLM/storage ports."""

    def _override_get_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_storage] = lambda: fake_storage
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": os.environ["OSCAR_API_KEY"]},
    ) as c:
        yield c
    app.dependency_overrides.clear()
