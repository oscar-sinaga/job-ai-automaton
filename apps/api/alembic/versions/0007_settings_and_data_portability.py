"""Persist CV defaults, generation preferences, and an artifact-deletion outbox.

Revision ID: 0007_settings
Revises: 0006_analytics_views
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_settings"
down_revision = "0006_analytics_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "default_cv_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "integration_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deletion_token_hash", sa.String(64), nullable=True),
        sa.Column("deletion_scope", sa.String(20), nullable=True),
        sa.Column("deletion_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deletion_counts", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "pending_file_deletions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("storage_uri", name="uq_pending_file_deletion_uri"),
    )
    op.add_column(
        "cv_generation_runs",
        sa.Column(
            "preferences", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )


def downgrade() -> None:
    op.drop_column("cv_generation_runs", "preferences")
    op.drop_table("pending_file_deletions")
    op.drop_table("user_settings")
