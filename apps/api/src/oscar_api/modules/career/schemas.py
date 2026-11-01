"""Pydantic schemas for the career module (docs/05_API_DESIGN.md §7)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field


class ExperienceIn(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: dt.date
    end_date: dt.date | None = None
    is_current: bool = False
    description: str | None = None


class ExperiencePatch(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    is_current: bool | None = None
    description: str | None = None


class ExperienceOut(ExperienceIn):
    id: int


class ProjectIn(BaseModel):
    name: str
    description: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    link: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    link: str | None = None


class ProjectOut(ProjectIn):
    id: int


class AchievementIn(BaseModel):
    statement: str
    experience_id: int | None = None
    project_id: int | None = None
    context: str | None = None
    metric_value: str | None = None
    metric_verified: bool = False
    skill_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    technology_tags: list[str] = Field(default_factory=list)
    verification_status: str = "unverified"
    notes: str | None = None


class AchievementPatch(BaseModel):
    statement: str | None = None
    experience_id: int | None = None
    project_id: int | None = None
    context: str | None = None
    metric_value: str | None = None
    metric_verified: bool | None = None
    skill_tags: list[str] | None = None
    domain_tags: list[str] | None = None
    technology_tags: list[str] | None = None
    verification_status: str | None = None
    notes: str | None = None


class AchievementOut(AchievementIn):
    id: int


class SkillIn(BaseModel):
    name: str
    category: str | None = None
    years_experience: float | None = None


class SkillPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    years_experience: float | None = None


class SkillOut(SkillIn):
    id: int


class EducationIn(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class EducationPatch(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class EducationOut(EducationIn):
    id: int


class CertificationIn(BaseModel):
    name: str
    issuer: str | None = None
    issued_date: dt.date | None = None
    expires_date: dt.date | None = None


class CertificationPatch(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issued_date: dt.date | None = None
    expires_date: dt.date | None = None


class CertificationOut(CertificationIn):
    id: int


class ApplicationProfilePatch(BaseModel):
    notice_period: str | None = None
    salary_expectation: str | None = None
    work_authorization: str | None = None
    relocation_ok: bool | None = None
    preferred_location: str | None = None
    links: dict[str, Any] | None = None


class ApplicationProfileOut(BaseModel):
    notice_period: str | None
    salary_expectation: str | None
    work_authorization: str | None
    relocation_ok: bool | None
    preferred_location: str | None
    links: dict[str, Any]


class CareerProfilePatch(BaseModel):
    summary: str | None = None


class CareerProfileOut(BaseModel):
    id: int
    summary: str | None
    experiences: list[ExperienceOut]
    projects: list[ProjectOut]
    achievements: list[AchievementOut]
    skills: list[SkillOut]
    education: list[EducationOut]
    certifications: list[CertificationOut]
    application_profile: ApplicationProfileOut
