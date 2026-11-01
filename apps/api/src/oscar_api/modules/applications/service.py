"""Applications module service layer.

`create_application` and `add_event` are the two places a status change can
happen post-capture; both write exactly one event and update
`jobs.current_status` in the same transaction (ADR-005).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from oscar_api.core.errors import NotFoundError
from oscar_api.modules.applications.models import Application, ApplicationAnswer, ApplicationEvent
from oscar_api.modules.applications.schemas import ApplicationAnswerIn
from oscar_api.modules.applications.state_machine import next_status
from oscar_api.modules.cv.models import CVVersion
from oscar_api.modules.jobs.models import Job
from oscar_api.modules.jobs.service import get_job_or_404


def get_application_or_404(session: Session, application_id: int) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise NotFoundError(f"Application {application_id} not found")
    return application


def create_application(
    session: Session, *, job_id: int, submitted_cv_version_id: int | None
) -> Application:
    job = get_job_or_404(session, job_id)
    new_status = next_status(job.current_status, "APPLICATION_SUBMITTED")

    if submitted_cv_version_id is not None:
        cv_version = session.get(CVVersion, submitted_cv_version_id)
        if cv_version is None or cv_version.job_id != job_id:
            raise NotFoundError(f"CV version {submitted_cv_version_id} not found for this job")
        session.execute(
            update(CVVersion)
            .where(CVVersion.job_id == job_id, CVVersion.id != submitted_cv_version_id)
            .values(is_submitted=False)
        )
        cv_version.is_submitted = True

    application = Application(job_id=job_id, submitted_cv_version_id=submitted_cv_version_id)
    session.add(application)
    session.flush()

    job.current_status = new_status
    session.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="APPLICATION_SUBMITTED",
            actor="user",
            event_metadata={},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(application)
    return application


def add_event(
    session: Session,
    application_id: int,
    *,
    event_type: str,
    occurred_at: dt.datetime | None,
    metadata: dict[str, Any],
) -> tuple[ApplicationEvent, Job]:
    application = get_application_or_404(session, application_id)
    job = session.get(Job, application.job_id)
    if job is None:
        raise NotFoundError(f"Job {application.job_id} not found")

    new_status = next_status(job.current_status, event_type)  # raises IllegalTransitionError

    event = ApplicationEvent(
        application_id=application.id,
        event_type=event_type,
        actor="user",
        event_metadata=metadata,
        occurred_at=occurred_at or dt.datetime.now(dt.UTC),
    )
    session.add(event)
    job.current_status = new_status
    session.commit()
    session.refresh(event)
    session.refresh(job)
    return event, job


def add_answer(
    session: Session, application_id: int, data: ApplicationAnswerIn
) -> ApplicationAnswer:
    get_application_or_404(session, application_id)
    answer = ApplicationAnswer(application_id=application_id, **data.model_dump())
    session.add(answer)
    session.commit()
    session.refresh(answer)
    return answer
