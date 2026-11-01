"""jobs capture: users, sources, companies, role_categories, jobs, raw snapshots, events

Milestone 1. Adds the tables FR-001..FR-003 and FR-009 need: capture a job from
desktop/mobile, store it durably alongside an immutable raw snapshot, and keep
an append-only event trail. Parsed data / skills arrive with the parser in M3
(docs/15_ROADMAP_AND_MILESTONES.md) -- not modelled yet.

Revision ID: 0002_jobs_capture
Revises: 0001_baseline
Create Date: 2026-08-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_jobs_capture"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_kind = postgresql.ENUM("job_board", "career_page", "referral", "other", name="source_kind")
capture_completeness = postgresql.ENUM(
    "CAPTURED_PARTIAL", "CAPTURED_COMPLETE", "NEEDS_ENRICHMENT", name="capture_completeness"
)
capture_method = postgresql.ENUM(
    "extension", "manual_url", "paste_text", "mobile_share", name="capture_method"
)
job_status = postgresql.ENUM(
    "SAVED",
    "READY_TO_APPLY",
    "APPLYING",
    "APPLIED",
    "ASSESSMENT",
    "INTERVIEW",
    "FINAL_INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
    "SKIPPED",
    name="job_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    # Create each enum type explicitly, then tell SQLAlchemy not to also
    # auto-create it via the table's before_create event when the same enum
    # object is reused as a column type below -- otherwise it tries to CREATE
    # TYPE twice and the second one raises DuplicateObject.
    for pg_enum in (source_kind, capture_completeness, capture_method, job_status):
        pg_enum.create(bind, checkfirst=True)
        pg_enum.create_type = False

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("kind", source_kind, nullable=False),
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("normalized_name", sa.String(300), nullable=False),
        sa.Column("domain", sa.String(300), nullable=True),
    )
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"])

    op.create_table(
        "role_categories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("ref", sa.String(16), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_id", sa.BigInteger(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("company_id", sa.BigInteger(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column(
            "role_category_id", sa.BigInteger(), sa.ForeignKey("role_categories.id"), nullable=True
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("capture_completeness", capture_completeness, nullable=False),
        sa.Column("current_status", job_status, nullable=False, server_default="SAVED"),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.Column("duplicate_of_job_id", sa.BigInteger(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("ref", name="uq_jobs_ref"),
    )
    op.create_index("ix_jobs_user_status", "jobs", ["user_id", "current_status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index(
        "ix_jobs_dedupe_key",
        "jobs",
        ["dedupe_key"],
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )
    op.create_index(
        "uq_jobs_idempotency_key",
        "jobs",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "job_raw_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "job_id", sa.BigInteger(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("page_title", sa.Text(), nullable=True),
        sa.Column("capture_method", capture_method, nullable=False),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_snapshots_job_captured", "job_raw_snapshots", ["job_id", "captured_at"])

    op.create_table(
        "job_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "job_id", sa.BigInteger(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(20), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_job_events_job_occurred", "job_events", ["job_id", "occurred_at"])
    op.create_index("ix_job_events_type_occurred", "job_events", ["event_type", "occurred_at"])

    # ADR-002: seed the single implicit V1 user; every user_id FK points here.
    op.execute(
        "INSERT INTO users (id, email, display_name) VALUES "
        "(1, 'oscar.m.sinaga@smmf.co.id', 'Oscar Michael Sinaga')"
    )
    op.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), 1, true)")


def downgrade() -> None:
    op.drop_table("job_events")
    op.drop_table("job_raw_snapshots")
    op.drop_index("uq_jobs_idempotency_key", table_name="jobs")
    op.drop_index("ix_jobs_dedupe_key", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_user_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("role_categories")
    op.drop_index("ix_companies_normalized_name", table_name="companies")
    op.drop_table("companies")
    op.drop_table("sources")
    op.drop_table("users")

    bind = op.get_bind()
    job_status.drop(bind, checkfirst=True)
    capture_method.drop(bind, checkfirst=True)
    capture_completeness.drop(bind, checkfirst=True)
    source_kind.drop(bind, checkfirst=True)
