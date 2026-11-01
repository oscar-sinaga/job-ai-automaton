"""CV module service layer: version CRUD, approval, export, submission."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from oscar_api.core.errors import ConflictError, NotFoundError, StorageError
from oscar_api.modules.cv.models import CVArtifact, CVVersion
from oscar_api.modules.cv.pdf import render_pdf
from oscar_api.modules.jobs.models import Job, JobEvent, JobEventType, JobStatus
from oscar_api.ports.storage import Storage


def get_version_or_404(session: Session, cv_version_id: int) -> CVVersion:
    version = session.get(CVVersion, cv_version_id)
    if version is None:
        raise NotFoundError(f"CV version {cv_version_id} not found")
    return version


def list_versions(session: Session, job_id: int) -> list[CVVersion]:
    return list(
        session.execute(
            select(CVVersion).where(CVVersion.job_id == job_id).order_by(CVVersion.version_number)
        )
        .scalars()
        .all()
    )


def edit_version(session: Session, cv_version_id: int, sections: dict[str, Any]) -> CVVersion:
    """Creates a NEW version rather than mutating (ADR-014): a version already
    referenced by a submitted application must stay byte-stable forever."""
    original = get_version_or_404(session, cv_version_id)
    latest_number = (
        session.execute(
            select(CVVersion.version_number)
            .where(CVVersion.job_id == original.job_id)
            .order_by(CVVersion.version_number.desc())
        )
        .scalars()
        .first()
        or 0
    )
    new_version = CVVersion(
        job_id=original.job_id,
        version_number=latest_number + 1,
        summary_text=(sections.get("summary") or {}).get("text"),
        sections=sections,
        is_submitted=False,
    )
    session.add(new_version)
    session.add(
        JobEvent(
            job_id=original.job_id,
            event_type=JobEventType.CV_EDITED.value,
            actor="user",
            event_metadata={"from_version": original.version_number},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(new_version)
    return new_version


def approve_version(session: Session, cv_version_id: int) -> CVVersion:
    version = get_version_or_404(session, cv_version_id)
    job = session.get(Job, version.job_id)
    if job is None:
        raise NotFoundError(f"Job {version.job_id} not found")

    # Full transition validation arrives with the state machine in M4; this is
    # the one pre-application transition CV Review itself needs.
    job.current_status = JobStatus.READY_TO_APPLY
    session.add(
        JobEvent(
            job_id=job.id,
            event_type=JobEventType.CV_APPROVED.value,
            actor="user",
            event_metadata={"cv_version_id": version.id},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(version)
    return version


def export_version(session: Session, storage: Storage, cv_version_id: int) -> CVArtifact:
    version = get_version_or_404(session, cv_version_id)
    pdf_bytes = render_pdf(version)

    try:
        uri = storage.save(relative_path=f"cv/{version.label}.pdf", data=pdf_bytes)
    except OSError as exc:
        raise StorageError(f"Could not write CV PDF: {exc}") from exc

    artifact = CVArtifact(cv_version_id=version.id, kind="pdf", storage_uri=uri)
    session.add(artifact)
    session.add(
        JobEvent(
            job_id=version.job_id,
            event_type=JobEventType.CV_EXPORTED.value,
            actor="user",
            event_metadata={"cv_version_id": version.id},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(artifact)
    return artifact


def mark_submitted(session: Session, cv_version_id: int) -> CVVersion:
    version = get_version_or_404(session, cv_version_id)
    session.execute(
        update(CVVersion)
        .where(CVVersion.job_id == version.job_id, CVVersion.id != version.id)
        .values(is_submitted=False)
    )
    version.is_submitted = True
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Could not mark this CV version as submitted") from exc
    session.refresh(version)
    return version
