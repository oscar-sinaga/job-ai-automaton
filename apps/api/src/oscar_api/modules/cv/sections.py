"""Snapshot verified text and career headings alongside each immutable version."""

from typing import Any

from oscar_api.modules.career.models import CareerProfile
from oscar_api.modules.cv.grounding import fact_id_of
from oscar_api.modules.cv.schemas import CVDraft


def snapshot_sections(draft: CVDraft, profile: CareerProfile) -> dict[str, Any]:
    sections = draft.model_dump(mode="json")
    links = profile.application_profile.links if profile.application_profile else {}
    sections["candidate"] = {
        key: str(links[f"cv_{key}"]).strip()
        for key in ("name", "email", "phone", "linkedin", "github", "portfolio")
        if links.get(f"cv_{key}")
    }
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
            start_date=exp.start_date.isoformat(),
            end_date=exp.end_date.isoformat() if exp.end_date else None,
            is_current=exp.is_current,
        )
    projects = {project.id: project for project in profile.projects}
    for proj_block in sections["projects"]:
        project = projects[proj_block["project_id"]]
        proj_block.update(name=project.name, link=project.link)
    return sections
