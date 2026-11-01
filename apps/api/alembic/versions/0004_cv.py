"""cv: versions, generation runs, artifacts

Milestone 3. FR-006/FR-007: grounded CV generation, review/versioning, and PDF
export. `cv_versions` rows are immutable once created (ADR-014) -- an edit
inserts a new version rather than updating one.

Revision ID: 0004_cv
Revises: 0003_career_profile
Create Date: 2026-08-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_cv"
down_revision: str | None = "0003_career_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cv_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "job_id", sa.BigInteger(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("is_submitted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("job_id", "version_number", name="uq_cv_versions_job_version"),
    )
    op.create_index(
        "uq_one_submitted_cv_per_job",
        "cv_versions",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("is_submitted"),
    )

    op.create_table(
        "cv_generation_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "job_id", sa.BigInteger(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "cv_version_id",
            sa.BigInteger(),
            sa.ForeignKey("cv_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "grounding_report",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_cv_runs_job", "cv_generation_runs", ["job_id"])

    op.create_table(
        "cv_artifacts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "cv_version_id",
            sa.BigInteger(),
            sa.ForeignKey("cv_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False, server_default="pdf"),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_cv_artifacts_version", "cv_artifacts", ["cv_version_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_artifacts_version", table_name="cv_artifacts")
    op.drop_table("cv_artifacts")
    op.drop_index("ix_cv_runs_job", table_name="cv_generation_runs")
    op.drop_table("cv_generation_runs")
    op.drop_index("uq_one_submitted_cv_per_job", table_name="cv_versions")
    op.drop_table("cv_versions")
