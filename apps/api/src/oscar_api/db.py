"""Database engine and session wiring.

``Base`` is the declarative base every module's ORM models inherit from, and
what Alembic's ``target_metadata`` points at.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from sqlalchemy import BigInteger, Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from oscar_api.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    ``Mapped[int]`` maps to BIGINT everywhere (docs/04 §1: "Primary keys: bigint
    generated always as identity") -- set once here instead of spelling out
    ``BigInteger`` on every id/FK column in every module.
    """

    type_annotation_map: ClassVar[dict[type, type]] = {int: BigInteger}


_settings = get_settings()

engine: Engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,  # a laptop that slept mid-session leaves dead connections behind
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database() -> bool:
    """Cheap liveness probe for ``/health``. Never raises."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
