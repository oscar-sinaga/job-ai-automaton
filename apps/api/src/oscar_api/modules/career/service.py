"""Career module service layer.

Six nested collections (experiences, projects, achievements, skills, education,
certifications) share one CRUD shape, so `_owned_or_404` is a small shared
helper rather than six near-identical lookup functions -- everything past that
point stays explicit per entity (docs/05 §7's own framing: "same CRUD shape per
entity", not a generic framework).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from oscar_api.core.errors import NotFoundError, ValidationFailedError
from oscar_api.core.models import SINGLE_USER_ID
from oscar_api.modules.career.models import (
    ApplicationProfile,
    CareerAchievement,
    CareerCertification,
    CareerEducation,
    CareerExperience,
    CareerProfile,
    CareerProject,
    CareerSkill,
)
from oscar_api.modules.career.schemas import (
    AchievementIn,
    AchievementPatch,
    ApplicationProfilePatch,
    CareerProfilePatch,
    CertificationIn,
    CertificationPatch,
    EducationIn,
    EducationPatch,
    ExperienceIn,
    ExperiencePatch,
    ProjectIn,
    ProjectPatch,
    SkillIn,
    SkillPatch,
)


def get_profile(session: Session) -> CareerProfile:
    """The single profile, seeded by migration alongside the single user (ADR-002)."""
    return session.execute(
        select(CareerProfile).where(CareerProfile.user_id == SINGLE_USER_ID)
    ).scalar_one()


def patch_profile(session: Session, patch: CareerProfilePatch) -> CareerProfile:
    profile = get_profile(session)
    if patch.summary is not None:
        profile.summary = patch.summary
        session.commit()
        session.refresh(profile)
    return profile


type _CollectionModel = (
    CareerExperience
    | CareerProject
    | CareerAchievement
    | CareerSkill
    | CareerEducation
    | CareerCertification
)


def _owned_or_404[M: _CollectionModel](
    session: Session, model: type[M], item_id: int, profile_id: int
) -> M:
    obj = session.get(model, item_id)
    if obj is None or obj.profile_id != profile_id:
        raise NotFoundError(f"{model.__name__} {item_id} not found")
    return obj


# ── Experiences ──────────────────────────────────────────────────────────────


def add_experience(session: Session, data: ExperienceIn) -> CareerExperience:
    profile = get_profile(session)
    exp = CareerExperience(profile_id=profile.id, **data.model_dump())
    session.add(exp)
    session.commit()
    session.refresh(exp)
    return exp


def patch_experience(session: Session, item_id: int, patch: ExperiencePatch) -> CareerExperience:
    profile = get_profile(session)
    exp = _owned_or_404(session, CareerExperience, item_id, profile.id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(exp, field, value)
    session.commit()
    session.refresh(exp)
    return exp


def delete_experience(session: Session, item_id: int) -> None:
    profile = get_profile(session)
    exp = _owned_or_404(session, CareerExperience, item_id, profile.id)
    session.delete(exp)
    session.commit()


# ── Projects ─────────────────────────────────────────────────────────────────


def add_project(session: Session, data: ProjectIn) -> CareerProject:
    profile = get_profile(session)
    project = CareerProject(profile_id=profile.id, **data.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def patch_project(session: Session, item_id: int, patch: ProjectPatch) -> CareerProject:
    profile = get_profile(session)
    project = _owned_or_404(session, CareerProject, item_id, profile.id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, item_id: int) -> None:
    profile = get_profile(session)
    project = _owned_or_404(session, CareerProject, item_id, profile.id)
    session.delete(project)
    session.commit()


# ── Achievements (the fact store CV grounding will cite in M3) ──────────────


def _validate_achievement_parent(session: Session, profile_id: int, data: AchievementIn) -> None:
    if data.experience_id is not None and data.project_id is not None:
        raise ValidationFailedError(
            "An achievement may belong to at most one of experience/project"
        )
    if data.experience_id is not None:
        _owned_or_404(session, CareerExperience, data.experience_id, profile_id)
    if data.project_id is not None:
        _owned_or_404(session, CareerProject, data.project_id, profile_id)


def _validate_metric(metric_verified: bool, metric_value: str | None) -> None:
    # Enforced in code, not left to the DB CHECK constraint to surface as a
    # raw 500 -- "an unverified metric may never appear as a number in a CV"
    # (docs/07 §2) starts here, at the point the fact is recorded.
    if metric_verified and not metric_value:
        raise ValidationFailedError("A verified metric must have a metric_value")


def add_achievement(session: Session, data: AchievementIn) -> CareerAchievement:
    profile = get_profile(session)
    _validate_achievement_parent(session, profile.id, data)
    _validate_metric(data.metric_verified, data.metric_value)
    achievement = CareerAchievement(profile_id=profile.id, **data.model_dump())
    session.add(achievement)
    session.commit()
    session.refresh(achievement)
    return achievement


def patch_achievement(session: Session, item_id: int, patch: AchievementPatch) -> CareerAchievement:
    profile = get_profile(session)
    achievement = _owned_or_404(session, CareerAchievement, item_id, profile.id)
    updates = patch.model_dump(exclude_unset=True)

    new_experience_id = updates.get("experience_id", achievement.experience_id)
    new_project_id = updates.get("project_id", achievement.project_id)
    if new_experience_id is not None and new_project_id is not None:
        raise ValidationFailedError(
            "An achievement may belong to at most one of experience/project"
        )
    if "experience_id" in updates and new_experience_id is not None:
        _owned_or_404(session, CareerExperience, new_experience_id, profile.id)
    if "project_id" in updates and new_project_id is not None:
        _owned_or_404(session, CareerProject, new_project_id, profile.id)

    new_metric_verified = updates.get("metric_verified", achievement.metric_verified)
    new_metric_value = updates.get("metric_value", achievement.metric_value)
    _validate_metric(new_metric_verified, new_metric_value)

    for field, value in updates.items():
        setattr(achievement, field, value)
    session.commit()
    session.refresh(achievement)
    return achievement


def delete_achievement(session: Session, item_id: int) -> None:
    """Soft delete (docs/05 §7): a CV version citing this fact must stay explainable."""
    profile = get_profile(session)
    achievement = _owned_or_404(session, CareerAchievement, item_id, profile.id)
    achievement.deleted_at = dt.datetime.now(dt.UTC)
    session.commit()


# ── Skills ───────────────────────────────────────────────────────────────────


def add_skill(session: Session, data: SkillIn) -> CareerSkill:
    profile = get_profile(session)
    skill = CareerSkill(profile_id=profile.id, **data.model_dump())
    session.add(skill)
    session.commit()
    session.refresh(skill)
    return skill


def patch_skill(session: Session, item_id: int, patch: SkillPatch) -> CareerSkill:
    profile = get_profile(session)
    skill = _owned_or_404(session, CareerSkill, item_id, profile.id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    session.commit()
    session.refresh(skill)
    return skill


def delete_skill(session: Session, item_id: int) -> None:
    profile = get_profile(session)
    skill = _owned_or_404(session, CareerSkill, item_id, profile.id)
    session.delete(skill)
    session.commit()


# ── Education ────────────────────────────────────────────────────────────────


def add_education(session: Session, data: EducationIn) -> CareerEducation:
    profile = get_profile(session)
    education = CareerEducation(profile_id=profile.id, **data.model_dump())
    session.add(education)
    session.commit()
    session.refresh(education)
    return education


def patch_education(session: Session, item_id: int, patch: EducationPatch) -> CareerEducation:
    profile = get_profile(session)
    education = _owned_or_404(session, CareerEducation, item_id, profile.id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(education, field, value)
    session.commit()
    session.refresh(education)
    return education


def delete_education(session: Session, item_id: int) -> None:
    profile = get_profile(session)
    education = _owned_or_404(session, CareerEducation, item_id, profile.id)
    session.delete(education)
    session.commit()


# ── Certifications ───────────────────────────────────────────────────────────


def add_certification(session: Session, data: CertificationIn) -> CareerCertification:
    profile = get_profile(session)
    cert = CareerCertification(profile_id=profile.id, **data.model_dump())
    session.add(cert)
    session.commit()
    session.refresh(cert)
    return cert


def patch_certification(
    session: Session, item_id: int, patch: CertificationPatch
) -> CareerCertification:
    profile = get_profile(session)
    cert = _owned_or_404(session, CareerCertification, item_id, profile.id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(cert, field, value)
    session.commit()
    session.refresh(cert)
    return cert


def delete_certification(session: Session, item_id: int) -> None:
    profile = get_profile(session)
    cert = _owned_or_404(session, CareerCertification, item_id, profile.id)
    session.delete(cert)
    session.commit()


# ── Application profile (1:1) ────────────────────────────────────────────────


def get_application_profile(session: Session) -> ApplicationProfile:
    profile = get_profile(session)
    assert profile.application_profile is not None  # seeded alongside the profile
    return profile.application_profile


def patch_application_profile(
    session: Session, patch: ApplicationProfilePatch
) -> ApplicationProfile:
    app_profile = get_application_profile(session)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(app_profile, field, value)
    session.commit()
    session.refresh(app_profile)
    return app_profile


# ── Full profile read (achievements exclude soft-deleted rows) ─────────────


def get_active_achievements(session: Session, profile_id: int) -> list[CareerAchievement]:
    return list(
        session.execute(
            select(CareerAchievement)
            .where(CareerAchievement.profile_id == profile_id)
            .where(CareerAchievement.deleted_at.is_(None))
            .order_by(CareerAchievement.id)
        )
        .scalars()
        .all()
    )
