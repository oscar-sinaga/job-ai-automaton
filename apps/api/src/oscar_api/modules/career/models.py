"""ORM models for the career domain (docs/04_DATA_MODEL.md §3).

`CareerAchievement` is the most important table in the system: every CV bullet
generated in Milestone 3 must cite one, by ID, as its supporting fact
(docs/07_CV_GROUNDING_AND_EVALS.md). `metric_verified` is what makes "an
unverified metric may never appear as a number in a CV" a checkable data
property instead of a prompt instruction.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oscar_api.db import Base


class CareerProfile(Base):
    __tablename__ = "career_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_career_profiles_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default="now()",
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    experiences: Mapped[list[CareerExperience]] = relationship(
        back_populates="profile", order_by="CareerExperience.start_date.desc()"
    )
    projects: Mapped[list[CareerProject]] = relationship(back_populates="profile")
    achievements: Mapped[list[CareerAchievement]] = relationship(back_populates="profile")
    skills: Mapped[list[CareerSkill]] = relationship(back_populates="profile")
    education: Mapped[list[CareerEducation]] = relationship(back_populates="profile")
    certifications: Mapped[list[CareerCertification]] = relationship(back_populates="profile")
    application_profile: Mapped[ApplicationProfile | None] = relationship(
        back_populates="profile", uselist=False
    )


class CareerExperience(Base):
    __tablename__ = "career_experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    company: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_date: Mapped[dt.date] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[CareerProfile] = relationship(back_populates="experiences")
    achievements: Mapped[list[CareerAchievement]] = relationship(back_populates="experience")


class CareerProject(Base):
    __tablename__ = "career_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[CareerProfile] = relationship(back_populates="projects")
    achievements: Mapped[list[CareerAchievement]] = relationship(back_populates="project")


class CareerAchievement(Base):
    """The atomic, citable fact (docs/07 §2). Soft-deleted only: a CV version
    that already cites one must remain explainable (docs/05 §7)."""

    __tablename__ = "career_achievements"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(experience_id, project_id) <= 1",
            name="achievement_single_parent",
        ),
        CheckConstraint(
            "NOT metric_verified OR metric_value IS NOT NULL",
            name="metric_verified_requires_value",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    experience_id: Mapped[int | None] = mapped_column(
        ForeignKey("career_experiences.id", ondelete="CASCADE"), nullable=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("career_projects.id", ondelete="CASCADE"), nullable=True
    )

    statement: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_verified: Mapped[bool] = mapped_column(default=False)

    skill_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    domain_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    technology_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default="now()"
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default="now()",
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )
    # Soft delete: NULL = active. A hard delete would leave a dangling
    # cv_versions.sections[].supporting_fact_ids reference once M3 exists.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    profile: Mapped[CareerProfile] = relationship(back_populates="achievements")
    experience: Mapped[CareerExperience | None] = relationship(back_populates="achievements")
    project: Mapped[CareerProject | None] = relationship(back_populates="achievements")


class CareerSkill(Base):
    __tablename__ = "career_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)

    profile: Mapped[CareerProfile] = relationship(back_populates="skills")


class CareerEducation(Base):
    __tablename__ = "career_education"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    institution: Mapped[str] = mapped_column(String(300))
    degree: Mapped[str | None] = mapped_column(String(200), nullable=True)
    field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    profile: Mapped[CareerProfile] = relationship(back_populates="education")


class CareerCertification(Base):
    __tablename__ = "career_certifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(300))
    issuer: Mapped[str | None] = mapped_column(String(300), nullable=True)
    issued_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    expires_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    profile: Mapped[CareerProfile] = relationship(back_populates="certifications")


class ApplicationProfile(Base):
    """Common application answers/preferences (docs/04 §3), 1:1 with the profile."""

    __tablename__ = "application_profiles"
    __table_args__ = (UniqueConstraint("profile_id", name="uq_application_profiles_profile"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("career_profiles.id", ondelete="CASCADE"))
    notice_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    salary_expectation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    relocation_ok: Mapped[bool | None] = mapped_column(nullable=True)
    preferred_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    links: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    profile: Mapped[CareerProfile] = relationship(back_populates="application_profile")
