"""Cross-cutting ORM models used by more than one domain module.

``User`` lives here rather than in a ``modules/users`` package because V1 has no
user-facing user management at all: a single row is seeded by migration 0002
(ADR-002) and every domain module's ``user_id`` foreign key points at it. There
is no signup flow, no auth-by-identity, and no reason to give it its own module.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from oscar_api.db import Base

# The one implicit user, seeded by migration 0002 (ADR-002). Every FK to
# `users.id` in this codebase points at this row.
SINGLE_USER_ID = 1


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
