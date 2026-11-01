"""career profile: the fact store CV grounding will cite in Milestone 3

Milestone 2. Adds FR-005's structured, editable source of truth: profile,
experiences, projects, achievements (the citable facts), skills, education,
certifications, and application preferences.

Revision ID: 0003_career_profile
Revises: 0002_jobs_capture
Create Date: 2026-08-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_career_profile"
down_revision: str | None = "0002_jobs_capture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("user_id", name="uq_career_profiles_user"),
    )

    op.create_table(
        "career_experiences",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company", sa.String(300), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_experiences_profile", "career_experiences", ["profile_id"])

    op.create_table(
        "career_projects",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
    )
    op.create_index("ix_projects_profile", "career_projects", ["profile_id"])

    op.create_table(
        "career_achievements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "experience_id",
            sa.BigInteger(),
            sa.ForeignKey("career_experiences.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("career_projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("metric_value", sa.Text(), nullable=True),
        sa.Column("metric_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "skill_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "domain_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "technology_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "verification_status", sa.String(20), nullable=False, server_default="unverified"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "num_nonnulls(experience_id, project_id) <= 1", name="achievement_single_parent"
        ),
        sa.CheckConstraint(
            "NOT metric_verified OR metric_value IS NOT NULL",
            name="metric_verified_requires_value",
        ),
    )
    op.create_index("ix_achievements_profile", "career_achievements", ["profile_id"])
    op.execute(
        "CREATE INDEX ix_achievements_skill_tags ON career_achievements USING gin (skill_tags)"
    )
    op.execute(
        "CREATE INDEX ix_achievements_technology_tags ON career_achievements "
        "USING gin (technology_tags)"
    )

    op.create_table(
        "career_skills",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("years_experience", sa.Numeric(4, 1), nullable=True),
    )
    op.create_index("ix_skills_profile", "career_skills", ["profile_id"])

    op.create_table(
        "career_education",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("institution", sa.String(300), nullable=False),
        sa.Column("degree", sa.String(200), nullable=True),
        sa.Column("field", sa.String(200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_education_profile", "career_education", ["profile_id"])

    op.create_table(
        "career_certifications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("issuer", sa.String(300), nullable=True),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expires_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_certifications_profile", "career_certifications", ["profile_id"])

    op.create_table(
        "application_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("career_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notice_period", sa.String(100), nullable=True),
        sa.Column("salary_expectation", sa.String(200), nullable=True),
        sa.Column("work_authorization", sa.String(200), nullable=True),
        sa.Column("relocation_ok", sa.Boolean(), nullable=True),
        sa.Column("preferred_location", sa.String(200), nullable=True),
        sa.Column(
            "links", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.UniqueConstraint("profile_id", name="uq_application_profiles_profile"),
    )

    # ADR-002: seed the single profile + application profile alongside the
    # single user, so `service.get_profile()` never has to handle "missing".
    op.execute("INSERT INTO career_profiles (id, user_id) VALUES (1, 1)")
    op.execute("SELECT setval(pg_get_serial_sequence('career_profiles', 'id'), 1, true)")
    op.execute("INSERT INTO application_profiles (id, profile_id) VALUES (1, 1)")
    op.execute("SELECT setval(pg_get_serial_sequence('application_profiles', 'id'), 1, true)")


def downgrade() -> None:
    op.drop_table("application_profiles")
    op.drop_index("ix_certifications_profile", table_name="career_certifications")
    op.drop_table("career_certifications")
    op.drop_index("ix_education_profile", table_name="career_education")
    op.drop_table("career_education")
    op.drop_index("ix_skills_profile", table_name="career_skills")
    op.drop_table("career_skills")
    op.drop_index("ix_achievements_technology_tags", table_name="career_achievements")
    op.drop_index("ix_achievements_skill_tags", table_name="career_achievements")
    op.drop_index("ix_achievements_profile", table_name="career_achievements")
    op.drop_table("career_achievements")
    op.drop_index("ix_projects_profile", table_name="career_projects")
    op.drop_table("career_projects")
    op.drop_index("ix_experiences_profile", table_name="career_experiences")
    op.drop_table("career_experiences")
    op.drop_table("career_profiles")
