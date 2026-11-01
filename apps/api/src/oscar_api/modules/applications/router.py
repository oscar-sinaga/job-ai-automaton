"""HTTP surface for the applications module (docs/05_API_DESIGN.md §6).

Two routers: `router` (prefix `/applications`) for everything scoped to one
application; `jobs_router` (prefix `/jobs`) for the one job-scoped lookup the
web UI needs -- "does this job already have an application" -- which lives
here (not in the jobs module) because jobs is a dependency leaf (docs/03 §2)
and must never import from applications.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from oscar_api.core.auth import require_api_key
from oscar_api.db import get_session
from oscar_api.modules.applications import service
from oscar_api.modules.applications.models import Application
from oscar_api.modules.applications.schemas import (
    ApplicationAnswerIn,
    ApplicationAnswerOut,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationEventIn,
    ApplicationEventOut,
    ApplicationOut,
)
from oscar_api.modules.jobs.models import Job

router = APIRouter(
    prefix="/applications", tags=["applications"], dependencies=[Depends(require_api_key)]
)
jobs_router = APIRouter(
    prefix="/jobs", tags=["applications"], dependencies=[Depends(require_api_key)]
)


def _to_out(application: Application, job: Job) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        submitted_cv_version_id=application.submitted_cv_version_id,
        current_status=job.current_status,
        created_at=application.created_at,
    )


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(
    data: ApplicationCreate, session: Session = Depends(get_session)
) -> ApplicationOut:
    application = service.create_application(
        session, job_id=data.job_id, submitted_cv_version_id=data.submitted_cv_version_id
    )
    job = session.get(Job, application.job_id)
    assert job is not None
    return _to_out(application, job)


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: int, session: Session = Depends(get_session)
) -> ApplicationDetail:
    application = service.get_application_or_404(session, application_id)
    job = session.get(Job, application.job_id)
    assert job is not None
    return ApplicationDetail(
        id=application.id,
        job_id=application.job_id,
        submitted_cv_version_id=application.submitted_cv_version_id,
        current_status=job.current_status,
        created_at=application.created_at,
        events=[
            {
                "event_type": e.event_type,
                "actor": e.actor,
                "metadata": e.event_metadata,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in application.events
        ],
    )


@router.post("/{application_id}/events", response_model=ApplicationEventOut)
def add_application_event(
    application_id: int, data: ApplicationEventIn, session: Session = Depends(get_session)
) -> ApplicationEventOut:
    event, job = service.add_event(
        session,
        application_id,
        event_type=data.event_type,
        occurred_at=data.occurred_at,
        metadata=data.metadata,
    )
    return ApplicationEventOut(event_id=event.id, current_status=job.current_status)


@router.post("/{application_id}/answers", response_model=ApplicationAnswerOut, status_code=201)
def add_application_answer(
    application_id: int, data: ApplicationAnswerIn, session: Session = Depends(get_session)
) -> ApplicationAnswerOut:
    answer = service.add_answer(session, application_id, data)
    return ApplicationAnswerOut(
        id=answer.id,
        question_key=answer.question_key,
        question_text=answer.question_text,
        answer_text=answer.answer_text,
        is_private=answer.is_private,
        source=answer.source,
    )


@jobs_router.get("/{job_id}/application", response_model=ApplicationOut | None)
def get_application_for_job(
    job_id: int, session: Session = Depends(get_session)
) -> ApplicationOut | None:
    """The most recent application for this job, or null if none exists yet
    -- lets the UI decide between "Mark as Applied" and the post-applied
    status buttons without the jobs module depending on applications."""
    application = (
        session.execute(
            select(Application).where(Application.job_id == job_id).order_by(Application.id.desc())
        )
        .scalars()
        .first()
    )
    if application is None:
        return None
    job = session.get(Job, job_id)
    assert job is not None
    return _to_out(application, job)
