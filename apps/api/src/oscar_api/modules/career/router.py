"""HTTP surface for the career module (docs/05_API_DESIGN.md §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from oscar_api.core.auth import require_api_key
from oscar_api.db import get_session
from oscar_api.modules.career import service
from oscar_api.modules.career.models import CareerProfile
from oscar_api.modules.career.schemas import (
    AchievementIn,
    AchievementOut,
    AchievementPatch,
    ApplicationProfileOut,
    ApplicationProfilePatch,
    CareerProfileOut,
    CareerProfilePatch,
    CertificationIn,
    CertificationOut,
    CertificationPatch,
    EducationIn,
    EducationOut,
    EducationPatch,
    ExperienceIn,
    ExperienceOut,
    ExperiencePatch,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    SkillIn,
    SkillOut,
    SkillPatch,
)

router = APIRouter(
    prefix="/career-profile", tags=["career"], dependencies=[Depends(require_api_key)]
)


def _to_profile_out(profile: CareerProfile, session: Session) -> CareerProfileOut:
    achievements = service.get_active_achievements(session, profile.id)
    assert profile.application_profile is not None
    return CareerProfileOut(
        id=profile.id,
        summary=profile.summary,
        experiences=[
            ExperienceOut.model_validate(e, from_attributes=True) for e in profile.experiences
        ],
        projects=[ProjectOut.model_validate(p, from_attributes=True) for p in profile.projects],
        achievements=[AchievementOut.model_validate(a, from_attributes=True) for a in achievements],
        skills=[SkillOut.model_validate(s, from_attributes=True) for s in profile.skills],
        education=[EducationOut.model_validate(e, from_attributes=True) for e in profile.education],
        certifications=[
            CertificationOut.model_validate(c, from_attributes=True) for c in profile.certifications
        ],
        application_profile=ApplicationProfileOut.model_validate(
            profile.application_profile, from_attributes=True
        ),
    )


@router.get("", response_model=CareerProfileOut)
def get_career_profile(session: Session = Depends(get_session)) -> CareerProfileOut:
    profile = service.get_profile(session)
    return _to_profile_out(profile, session)


@router.patch("", response_model=CareerProfileOut)
def patch_career_profile(
    patch: CareerProfilePatch, session: Session = Depends(get_session)
) -> CareerProfileOut:
    profile = service.patch_profile(session, patch)
    return _to_profile_out(profile, session)


@router.post("/experiences", response_model=ExperienceOut, status_code=201)
def add_experience(data: ExperienceIn, session: Session = Depends(get_session)) -> ExperienceOut:
    return ExperienceOut.model_validate(service.add_experience(session, data), from_attributes=True)


@router.patch("/experiences/{item_id}", response_model=ExperienceOut)
def patch_experience(
    item_id: int, patch: ExperiencePatch, session: Session = Depends(get_session)
) -> ExperienceOut:
    exp = service.patch_experience(session, item_id, patch)
    return ExperienceOut.model_validate(exp, from_attributes=True)


@router.delete("/experiences/{item_id}", status_code=204)
def delete_experience(item_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_experience(session, item_id)


@router.post("/projects", response_model=ProjectOut, status_code=201)
def add_project(data: ProjectIn, session: Session = Depends(get_session)) -> ProjectOut:
    return ProjectOut.model_validate(service.add_project(session, data), from_attributes=True)


@router.patch("/projects/{item_id}", response_model=ProjectOut)
def patch_project(
    item_id: int, patch: ProjectPatch, session: Session = Depends(get_session)
) -> ProjectOut:
    return ProjectOut.model_validate(
        service.patch_project(session, item_id, patch), from_attributes=True
    )


@router.delete("/projects/{item_id}", status_code=204)
def delete_project(item_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_project(session, item_id)


@router.post("/achievements", response_model=AchievementOut, status_code=201)
def add_achievement(data: AchievementIn, session: Session = Depends(get_session)) -> AchievementOut:
    return AchievementOut.model_validate(
        service.add_achievement(session, data), from_attributes=True
    )


@router.patch("/achievements/{item_id}", response_model=AchievementOut)
def patch_achievement(
    item_id: int, patch: AchievementPatch, session: Session = Depends(get_session)
) -> AchievementOut:
    return AchievementOut.model_validate(
        service.patch_achievement(session, item_id, patch), from_attributes=True
    )


@router.delete("/achievements/{item_id}", status_code=204)
def delete_achievement(item_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_achievement(session, item_id)


@router.post("/skills", response_model=SkillOut, status_code=201)
def add_skill(data: SkillIn, session: Session = Depends(get_session)) -> SkillOut:
    return SkillOut.model_validate(service.add_skill(session, data), from_attributes=True)


@router.patch("/skills/{item_id}", response_model=SkillOut)
def patch_skill(
    item_id: int, patch: SkillPatch, session: Session = Depends(get_session)
) -> SkillOut:
    return SkillOut.model_validate(
        service.patch_skill(session, item_id, patch), from_attributes=True
    )


@router.delete("/skills/{item_id}", status_code=204)
def delete_skill(item_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_skill(session, item_id)


@router.post("/education", response_model=EducationOut, status_code=201)
def add_education(data: EducationIn, session: Session = Depends(get_session)) -> EducationOut:
    return EducationOut.model_validate(service.add_education(session, data), from_attributes=True)


@router.patch("/education/{item_id}", response_model=EducationOut)
def patch_education(
    item_id: int, patch: EducationPatch, session: Session = Depends(get_session)
) -> EducationOut:
    return EducationOut.model_validate(
        service.patch_education(session, item_id, patch), from_attributes=True
    )


@router.delete("/education/{item_id}", status_code=204)
def delete_education(item_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_education(session, item_id)


@router.post("/certifications", response_model=CertificationOut, status_code=201)
def add_certification(
    data: CertificationIn, session: Session = Depends(get_session)
) -> CertificationOut:
    return CertificationOut.model_validate(
        service.add_certification(session, data), from_attributes=True
    )


@router.patch("/certifications/{item_id}", response_model=CertificationOut)
def patch_certification(
    item_id: int, patch: CertificationPatch, session: Session = Depends(get_session)
) -> CertificationOut:
    return CertificationOut.model_validate(
        service.patch_certification(session, item_id, patch), from_attributes=True
    )


@router.delete("/certifications/{item_id}", status_code=204)
def delete_certification(item_id: int, session: Session = Depends(get_session)) -> None:
    service.delete_certification(session, item_id)


@router.get("/application-profile", response_model=ApplicationProfileOut)
def get_application_profile(session: Session = Depends(get_session)) -> ApplicationProfileOut:
    return ApplicationProfileOut.model_validate(
        service.get_application_profile(session), from_attributes=True
    )


@router.patch("/application-profile", response_model=ApplicationProfileOut)
def patch_application_profile(
    patch: ApplicationProfilePatch, session: Session = Depends(get_session)
) -> ApplicationProfileOut:
    return ApplicationProfileOut.model_validate(
        service.patch_application_profile(session, patch), from_attributes=True
    )
