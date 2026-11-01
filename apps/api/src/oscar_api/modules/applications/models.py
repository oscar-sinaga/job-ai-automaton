"""ORM models for the applications domain (docs/04_DATA_MODEL.md §6).

No `current_status` column here -- `jobs.current_status` is the sole
materialized status (ADR-005). `application_events` is append-only and is the
actual source of truth for status history.
"""

from __future__ import annotations

import datetime as dt
import enum
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oscar_api.db import Base


class ApplicationEventType(enum.StrEnum):
    """Constants for `application_events.event_type` (docs/04 §6) -- a plain
    string column, same rationale as `JobEventType`."""

    APPLICATION_STARTED = "APPLICATION_STARTED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    ASSESSMENT_RECEIVED = "ASSESSMENT_RECEIVED"
    INTERVIEW_RECEIVED = "INTERVIEW_RECEIVED"
    INTERVIEW_COMPLETED = "INTERVIEW_COMPLETED"
    FINAL_INTERVIEW = "FINAL_INTERVIEW"
    REJECTED = "REJECTED"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    WITHDRAWN = "WITHDRAWN"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    submitted_cv_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_versions.id"), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default="now()",
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application", order_by="ApplicationEvent.occurred_at"
    )
    answers: Mapped[list[ApplicationAnswer]] = relationship(back_populates="application")


class ApplicationEvent(Base):
    """Append-only (FR-009). The source of truth for post-APPLIED status history."""

    __tablename__ = "application_events"
    __table_args__ = (
        Index("ix_application_events_app_occurred", "application_id", "occurred_at"),
        Index("ix_application_events_type_occurred", "event_type", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(20))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    application: Mapped[Application] = relationship(back_populates="events")


class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    question_key: Mapped[str] = mapped_column(String(100))
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_text: Mapped[str] = mapped_column(Text)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # profile | ai_draft | manual

    application: Mapped[Application] = relationship(back_populates="answers")
