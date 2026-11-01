"""ORM models for the jobs domain (docs/04_DATA_MODEL.md §4).

Only what Milestone 1 needs: capture, raw snapshots, dedupe, job events, and the
lookup tables jobs reference. Parsed data and skills (parser output) arrive with
the ``job_parser`` agent in Milestone 3 -- they are not modelled yet.
"""

from __future__ import annotations

import datetime as dt
import enum
from typing import Any

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oscar_api.db import Base


class SourceKind(enum.StrEnum):
    job_board = "job_board"
    career_page = "career_page"
    referral = "referral"
    other = "other"


class CaptureCompleteness(enum.StrEnum):
    """Server-derived, never trusted from the client (ADR-012)."""

    CAPTURED_PARTIAL = "CAPTURED_PARTIAL"
    CAPTURED_COMPLETE = "CAPTURED_COMPLETE"
    NEEDS_ENRICHMENT = "NEEDS_ENRICHMENT"


class CaptureMethod(enum.StrEnum):
    extension = "extension"
    manual_url = "manual_url"
    paste_text = "paste_text"
    mobile_share = "mobile_share"


class JobStatus(enum.StrEnum):
    """The 11 statuses (docs/04 §6). Transition legality is enforced in M4."""

    SAVED = "SAVED"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    ASSESSMENT = "ASSESSMENT"
    INTERVIEW = "INTERVIEW"
    FINAL_INTERVIEW = "FINAL_INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    SKIPPED = "SKIPPED"


class JobEventType(enum.StrEnum):
    """Constants for `job_events.event_type`, a plain string column (docs/04 §6) --
    new event types can be added without a migration, so this is not a DB enum."""

    JOB_SAVED = "JOB_SAVED"
    JOB_UPDATED = "JOB_UPDATED"
    JOB_PARSED = "JOB_PARSED"
    JOB_PARSE_CORRECTED = "JOB_PARSE_CORRECTED"
    CV_GENERATED = "CV_GENERATED"
    CV_REGENERATED = "CV_REGENERATED"
    CV_EDITED = "CV_EDITED"
    CV_APPROVED = "CV_APPROVED"
    CV_EXPORTED = "CV_EXPORTED"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind, name="source_kind"))


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    domain: Mapped[str | None] = mapped_column(String(300), nullable=True)


class RoleCategory(Base):
    __tablename__ = "role_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_user_status", "user_id", "current_status"),
        Index("ix_jobs_created_at", "created_at"),
        Index(
            "ix_jobs_dedupe_key",
            "dedupe_key",
            postgresql_where="dedupe_key IS NOT NULL",
        ),
        UniqueConstraint("ref", name="uq_jobs_ref"),
        Index(
            "uq_jobs_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human-facing ref ("J001"), assigned after insert once `id` is known
    # (docs/04 §1) -- simpler than a separate sequence.
    ref: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    role_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("role_categories.id"), nullable=True
    )

    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    capture_completeness: Mapped[CaptureCompleteness] = mapped_column(
        Enum(CaptureCompleteness, name="capture_completeness")
    )
    current_status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.SAVED
    )

    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default="now()",
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    snapshots: Mapped[list[JobRawSnapshot]] = relationship(
        back_populates="job", order_by="JobRawSnapshot.captured_at"
    )
    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job", order_by="JobEvent.occurred_at"
    )
    source: Mapped[Source | None] = relationship()
    company: Mapped[Company | None] = relationship()


class JobRawSnapshot(Base):
    """Append-only. No `updated_at` by design -- a snapshot is never modified (FR-003)."""

    __tablename__ = "job_raw_snapshots"
    __table_args__ = (Index("ix_snapshots_job_captured", "job_id", "captured_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    capture_method: Mapped[CaptureMethod] = mapped_column(
        Enum(CaptureMethod, name="capture_method")
    )
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    captured_at: Mapped[dt.datetime] = mapped_column(TIMESTAMP(timezone=True))

    job: Mapped[Job] = relationship(back_populates="snapshots")


class JobEvent(Base):
    """Append-only (FR-009). The source of truth for status history."""

    __tablename__ = "job_events"
    __table_args__ = (
        Index("ix_job_events_job_occurred", "job_id", "occurred_at"),
        Index("ix_job_events_type_occurred", "event_type", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(20))
    # DB column is named `metadata`; the Python attribute can't be, since
    # `metadata` is reserved on every SQLAlchemy declarative model (it's the
    # class's MetaData object).
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )

    job: Mapped[Job] = relationship(back_populates="events")
