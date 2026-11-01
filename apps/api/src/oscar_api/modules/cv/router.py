"""HTTP surface for the CV module (docs/05_API_DESIGN.md §5).

Two routers: `jobs_router` mounts under `/jobs/{job_id}/...` (generation,
version listing); `cv_router` mounts under `/cv/{cv_id}/...` (everything that
operates on one already-generated version).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from oscar_api.core.auth import require_api_key
from oscar_api.db import get_session
from oscar_api.modules.cv import generator, service
from oscar_api.modules.cv.deps import get_llm_provider, get_storage
from oscar_api.modules.cv.models import CVVersion
from oscar_api.modules.cv.schemas import (
    CVEditRequest,
    CVExportResponse,
    CVGenerationRunOut,
    CVVersionOut,
    CVVersionSummary,
    GenerateCVRequest,
    GenerateCVResponse,
)
from oscar_api.ports.llm import LLMProvider
from oscar_api.ports.storage import Storage

jobs_router = APIRouter(prefix="/jobs", tags=["cv"], dependencies=[Depends(require_api_key)])
cv_router = APIRouter(prefix="/cv", tags=["cv"], dependencies=[Depends(require_api_key)])


def _to_out(version: CVVersion) -> CVVersionOut:
    return CVVersionOut(
        id=version.id,
        job_id=version.job_id,
        version_number=version.version_number,
        label=version.label,
        summary_text=version.summary_text,
        sections=version.sections,
        is_submitted=version.is_submitted,
        created_at=version.created_at,
    )


@jobs_router.post("/{job_id}/generate-cv", response_model=GenerateCVResponse, status_code=201)
async def generate_cv(
    job_id: int,
    request: GenerateCVRequest,
    session: Session = Depends(get_session),
    llm: LLMProvider = Depends(get_llm_provider),
) -> GenerateCVResponse:
    cv_version, run, report, missing = await generator.generate_cv(
        session, llm, job_id=job_id, request=request
    )
    return GenerateCVResponse(
        cv_version_id=cv_version.id,
        label=cv_version.label,
        sections=cv_version.sections,
        missing_requirements=missing,
        grounding_report=report,
        run=CVGenerationRunOut(
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            input_tokens=run.input_tokens or 0,
            output_tokens=run.output_tokens or 0,
            latency_ms=run.latency_ms or 0,
        ),
    )


@jobs_router.get("/{job_id}/cv-versions", response_model=list[CVVersionSummary])
def list_cv_versions(
    job_id: int, session: Session = Depends(get_session)
) -> list[CVVersionSummary]:
    return [
        CVVersionSummary(
            id=v.id,
            version_number=v.version_number,
            is_submitted=v.is_submitted,
            created_at=v.created_at,
        )
        for v in service.list_versions(session, job_id)
    ]


@cv_router.get("/{cv_id}", response_model=CVVersionOut)
def get_cv(cv_id: int, session: Session = Depends(get_session)) -> CVVersionOut:
    return _to_out(service.get_version_or_404(session, cv_id))


@cv_router.patch("/{cv_id}", response_model=CVVersionOut)
def edit_cv(
    cv_id: int, request: CVEditRequest, session: Session = Depends(get_session)
) -> CVVersionOut:
    return _to_out(service.edit_version(session, cv_id, request.sections))


@cv_router.post("/{cv_id}/approve", response_model=CVVersionOut)
def approve_cv(cv_id: int, session: Session = Depends(get_session)) -> CVVersionOut:
    return _to_out(service.approve_version(session, cv_id))


@cv_router.post("/{cv_id}/export", response_model=CVExportResponse, status_code=201)
def export_cv(
    cv_id: int, session: Session = Depends(get_session), storage: Storage = Depends(get_storage)
) -> CVExportResponse:
    artifact = service.export_version(session, storage, cv_id)
    return CVExportResponse(artifact_id=artifact.id, storage_uri=artifact.storage_uri)


@cv_router.post("/{cv_id}/mark-submitted", response_model=CVVersionOut)
def mark_submitted(cv_id: int, session: Session = Depends(get_session)) -> CVVersionOut:
    return _to_out(service.mark_submitted(session, cv_id))
