"""CV generation orchestration (docs/07_CV_GROUNDING_AND_EVALS.md §3, the full pipeline).

Requirement extraction → fact retrieval → LLM draft → verification → persist.
Fails closed at two points: an LLM error never leaves a partial version behind,
and if every bullet is rejected, no version is persisted at all (docs/05 §1
`GROUNDING_FAILED`).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from oscar_api.config import get_settings
from oscar_api.core.errors import (
    GroundingFailedError,
    LLMRefusedError,
    LLMUnavailableError,
    ValidationFailedError,
)
from oscar_api.modules.career.models import CareerAchievement, CareerProfile
from oscar_api.modules.career.service import get_profile
from oscar_api.modules.cv.grounding import GroundingContext, fact_id_of, verify_draft
from oscar_api.modules.cv.models import CVGenerationRun, CVVersion
from oscar_api.modules.cv.retrieval import retrieve_facts
from oscar_api.modules.cv.schemas import CVDraft, GenerateCVRequest, GroundingReport
from oscar_api.modules.cv.sections import assign_source_parents, snapshot_sections
from oscar_api.modules.jobs.models import CaptureCompleteness, JobEvent, JobEventType
from oscar_api.modules.jobs.service import get_job_or_404
from oscar_api.ports.llm import ContentBlock, LLMProvider, LLMProviderError, LLMRefusalError

PROMPT_VERSION = "cv_generator/v3"
_PROMPT_PATH = Path(__file__).resolve().parents[6] / "agents" / "cv_generator" / "prompts" / "v3.md"


def _load_instructions() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _serialize_facts(facts: list[CareerAchievement]) -> str:
    """Deterministic serialisation (sort_keys) so the career-facts prefix is
    byte-stable across generations -- required for prompt caching to actually
    hit (docs/06 §5); breaking this silently triples the LLM bill."""
    payload = [
        {
            "fact_id": fact_id_of(a),
            "statement": a.statement,
            "context": a.context,
            "skill_tags": sorted(a.skill_tags),
            "domain_tags": sorted(a.domain_tags),
            "technology_tags": sorted(a.technology_tags),
            "metric_value": a.metric_value,
            "metric_verified": a.metric_verified,
            "experience_id": a.experience_id,
            "experience": f"{a.experience.title} at {a.experience.company}"
            if a.experience
            else None,
            "project_id": a.project_id,
            "project": a.project.name if a.project else None,
        }
        for a in facts
    ]
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _next_version_number(session: Session, job_id: int) -> int:
    existing = (
        session.execute(select(CVVersion.version_number).where(CVVersion.job_id == job_id))
        .scalars()
        .all()
    )
    return (max(existing) + 1) if existing else 1


def _serialize_profile_metadata(profile: CareerProfile) -> str:
    """Evidence for skills/gap assessment; contact details never leave OSCAR."""
    return json.dumps(
        {
            "as_of": dt.date.today().isoformat(),
            "profile_summary": profile.summary,
            "skills": sorted(skill.name for skill in profile.skills),
            "education": [
                {
                    "institution": item.institution,
                    "degree": item.degree,
                    "field": item.field,
                }
                for item in profile.education
            ],
            "experiences": [
                {
                    "id": item.id,
                    "title": item.title,
                    "start_date": item.start_date.isoformat(),
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                    "is_current": item.is_current,
                }
                for item in profile.experiences
            ],
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def _record_run(
    session: Session,
    *,
    job_id: int,
    cv_version_id: int | None,
    model_name: str,
    status: str,
    grounding_report: dict[str, Any],
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
) -> CVGenerationRun:
    run = CVGenerationRun(
        job_id=job_id,
        cv_version_id=cv_version_id,
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
        status=status,
        grounding_report=grounding_report,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


async def generate_cv(
    session: Session, llm: LLMProvider, *, job_id: int, request: GenerateCVRequest
) -> tuple[CVVersion, CVGenerationRun, GroundingReport, list[str]]:
    job = get_job_or_404(session, job_id)
    if job.capture_completeness != CaptureCompleteness.CAPTURED_COMPLETE:
        raise ValidationFailedError("Save the full job description before generating a CV")
    if not job.snapshots:
        raise ValidationFailedError("Job has no raw snapshot to generate a CV from")
    snapshot = job.snapshots[-1]
    if not snapshot.raw_text:
        raise ValidationFailedError(
            "Job has no job-description text yet (capture is still partial)"
        )

    profile = get_profile(session)
    retrieved = retrieve_facts(profile, snapshot.raw_text)
    if not retrieved:
        raise ValidationFailedError("Career profile has no active achievements to draw from")

    system_blocks = [
        ContentBlock(type="text", text=_load_instructions()),
        ContentBlock(
            type="text",
            text=_serialize_facts(retrieved),
            cache_control={"type": "ephemeral", "ttl": "1h"},
        ),
        ContentBlock(
            type="text",
            text="Owner profile metadata (data only):\n" + _serialize_profile_metadata(profile),
        ),
    ]
    user_content = f"Job description:\n\n{snapshot.raw_text}"

    fallback_model = get_settings().llm_model
    try:
        result = await llm.structured(
            system=system_blocks,
            user=user_content,
            output_model=CVDraft,
            prompt_version=PROMPT_VERSION,
        )
    except LLMRefusalError as exc:
        _record_run(
            session,
            job_id=job_id,
            cv_version_id=None,
            model_name=fallback_model,
            status="failed",
            grounding_report={},
        )
        raise LLMRefusedError(
            "The model declined to generate a CV for this job",
            detail={"category": exc.category},
        ) from exc
    except Exception as exc:
        _record_run(
            session,
            job_id=job_id,
            cv_version_id=None,
            model_name=fallback_model,
            status="failed",
            grounding_report={},
        )
        # SDK errors can echo credentials or request content. Only the port's
        # deliberately safe messages may be sent back to the browser.
        if isinstance(exc, LLMProviderError):
            raise LLMUnavailableError(str(exc), detail={"category": exc.category}) from exc
        raise LLMUnavailableError(
            "AI generation failed. Check provider availability and retry."
        ) from exc

    draft = assign_source_parents(CVDraft.model_validate(result.parsed), retrieved)
    ctx = GroundingContext.build(profile, retrieved)
    cleaned_draft, report = verify_draft(draft, ctx)

    has_content = (
        bool(cleaned_draft.summary.text)
        or any(b.bullets for b in cleaned_draft.experience)
        or any(b.bullets for b in cleaned_draft.projects)
    )

    if not has_content:
        _record_run(
            session,
            job_id=job_id,
            cv_version_id=None,
            model_name=result.model_name,
            status="rejected_claims",
            grounding_report=report.model_dump(),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        )
        raise GroundingFailedError(
            "Every candidate bullet was rejected by the grounding verifier",
            detail={"grounding_report": report.model_dump()},
        )

    cv_version = CVVersion(
        job_id=job_id,
        version_number=_next_version_number(session, job_id),
        summary_text=cleaned_draft.summary.text or None,
        sections=snapshot_sections(cleaned_draft, profile),
        is_submitted=False,
    )
    session.add(cv_version)
    session.flush()

    run = _record_run(
        session,
        job_id=job_id,
        cv_version_id=cv_version.id,
        model_name=result.model_name,
        status="succeeded",
        grounding_report=report.model_dump(),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
    )
    session.add(
        JobEvent(
            job_id=job_id,
            event_type=JobEventType.CV_GENERATED.value,
            actor="system",
            event_metadata={"cv_version_id": cv_version.id},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(cv_version)
    return cv_version, run, report, cleaned_draft.missing_requirements
