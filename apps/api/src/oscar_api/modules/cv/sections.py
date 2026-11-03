"""Snapshot verified text and career headings alongside each immutable version."""

from typing import Any

from oscar_api.modules.career.models import CareerAchievement, CareerProfile
from oscar_api.modules.cv.grounding import fact_id_of
from oscar_api.modules.cv.schemas import (
    CVDraft,
    DraftBullet,
    DraftExperienceBlock,
    DraftProjectBlock,
)


def assign_source_parents(draft: CVDraft, facts: list[CareerAchievement]) -> CVDraft:
    """Place model-selected text under its source record before verification.

    Concurrent roles at the same employer can confuse model grouping. Parent
    metadata is deterministic: move a bullet only when ALL cited IDs resolve
    to one nonempty source parent. Unknown/mixed/orphan citations are left for
    the unchanged verifier to reject. No wording, citation, or metric is edited.
    """
    by_id = {fact_id_of(fact): fact for fact in facts}
    grouped: dict[tuple[str, int], list[DraftBullet]] = {}
    blocks = [
        *(("experience", block.experience_id, block.bullets) for block in draft.experience),
        *(("project", block.project_id, block.bullets) for block in draft.projects),
    ]
    for kind, parent_id, bullets in blocks:
        for bullet in bullets:
            parent = (kind, parent_id)
            if bullet.supporting_fact_ids and all(
                fid in by_id for fid in bullet.supporting_fact_ids
            ):
                cited = [by_id[fid] for fid in bullet.supporting_fact_ids]
                parents = {(fact.experience_id, fact.project_id) for fact in cited}
                if len(parents) == 1:
                    experience_id, project_id = next(iter(parents))
                    if experience_id is not None and project_id is None:
                        parent = ("experience", experience_id)
                    elif project_id is not None and experience_id is None:
                        parent = ("project", project_id)
            grouped.setdefault(parent, []).append(bullet)
    return draft.model_copy(
        update={
            "experience": [
                DraftExperienceBlock(experience_id=parent_id, bullets=bullets)
                for (kind, parent_id), bullets in grouped.items()
                if kind == "experience"
            ],
            "projects": [
                DraftProjectBlock(project_id=parent_id, bullets=bullets)
                for (kind, parent_id), bullets in grouped.items()
                if kind == "project"
            ],
        }
    )


def snapshot_sections(draft: CVDraft, profile: CareerProfile) -> dict[str, Any]:
    sections = draft.model_dump(mode="json")
    links = profile.application_profile.links if profile.application_profile else {}
    sections["candidate"] = {
        key: str(links[f"cv_{key}"]).strip()
        for key in ("name", "email", "phone", "linkedin", "github", "portfolio", "location")
        if links.get(f"cv_{key}")
    }
    # Freeze owner-entered education and credentials with each version.
    sections["education"] = [
        {
            "institution": item.institution,
            "degree": item.degree,
            "field": item.field,
            "start_date": item.start_date.isoformat() if item.start_date else None,
            "end_date": item.end_date.isoformat() if item.end_date else None,
        }
        for item in profile.education
    ]
    sections["certifications"] = [
        {
            "name": item.name,
            "issuer": item.issuer,
            "issued_date": item.issued_date.isoformat() if item.issued_date else None,
        }
        for item in profile.certifications
    ]
    cited = set(draft.summary.supporting_fact_ids)
    for block in draft.experience:
        for bullet in block.bullets:
            cited.update(bullet.supporting_fact_ids)
    for project_block in draft.projects:
        for bullet in project_block.bullets:
            cited.update(bullet.supporting_fact_ids)
    sections["source_facts"] = {
        fact_id_of(a): a.statement for a in profile.achievements if fact_id_of(a) in cited
    }
    experiences = {exp.id: exp for exp in profile.experiences}
    for exp_block in sections["experience"]:
        exp = experiences[exp_block["experience_id"]]
        exp_block.update(
            company=exp.company,
            title=exp.title,
            location=exp.location,
            start_date=exp.start_date.isoformat(),
            end_date=exp.end_date.isoformat() if exp.end_date else None,
            is_current=exp.is_current,
        )
    projects = {project.id: project for project in profile.projects}
    for proj_block in sections["projects"]:
        project = projects[proj_block["project_id"]]
        proj_block.update(
            name=project.name,
            link=project.link,
            start_date=project.start_date.isoformat() if project.start_date else None,
            end_date=project.end_date.isoformat() if project.end_date else None,
        )
    return sections
