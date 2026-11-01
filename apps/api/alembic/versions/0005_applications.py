"""applications: applications, application_events, application_answers

Milestone 4. FR-008/FR-009: application tracking with an append-only event
trail. No `current_status` column on `applications` -- `jobs.current_status`
is the sole materialized status (ADR-005); this table only records which job
an application is for and which CV version was submitted.

Revision ID: 0005_applications
Revises: 0004_cv
Create Date: 2026-08-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_applications"
down_revision: str | None = "0004_cv"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "job_id", sa.BigInteger(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "submitted_cv_version_id",
            sa.BigInteger(),
            sa.ForeignKey("cv_versions.id"),
            nullable=True,
        ),
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
    )
    op.create_index("ix_applications_job", "applications", ["job_id"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "application_id",
            sa.BigInteger(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
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
    op.create_index(
        "ix_application_events_app_occurred",
        "application_events",
        ["application_id", "occurred_at"],
    )
    op.create_index(
        "ix_application_events_type_occurred", "application_events", ["event_type", "occurred_at"]
    )

    op.create_table(
        "application_answers",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "application_id",
            sa.BigInteger(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(100), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
    )
    op.create_index("ix_application_answers_app", "application_answers", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_application_answers_app", table_name="application_answers")
    op.drop_table("application_answers")
    op.drop_index("ix_application_events_type_occurred", table_name="application_events")
    op.drop_index("ix_application_events_app_occurred", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_applications_job", table_name="applications")
    op.drop_table("applications")
