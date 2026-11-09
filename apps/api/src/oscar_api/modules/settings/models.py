"""Settings are user data; deletion tokens and cleanup jobs are operational state."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from oscar_api.db import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    default_cv_preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    integration_preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    deletion_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deletion_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    deletion_expires_at: Mapped[dt.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    deletion_counts: Mapped[dict[str, int] | None] = mapped_column(JSONB, nullable=True)


class PendingFileDeletion(Base):
    """Committed outbox: failed unlinks can be retried without resurrecting rows."""

    __tablename__ = "pending_file_deletions"
    __table_args__ = (UniqueConstraint("storage_uri", name="uq_pending_file_deletion_uri"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    storage_uri: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
