"""CV module service layer: version CRUD, approval, export, submission."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fpdf.errors import FPDFException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from oscar_api.core.errors import ConflictError, NotFoundError, StorageError, ValidationFailedError
from oscar_api.modules.applications.models import Application
from oscar_api.modules.career.service import get_profile
from oscar_api.modules.cv.grounding import GroundingContext, verify_draft
from oscar_api.modules.cv.models import CVArtifact, CVVersion
from oscar_api.modules.cv.pdf import render_pdf
from oscar_api.modules.cv.schemas import CVDraft
from oscar_api.modules.cv.sections import snapshot_sections
from oscar_api.modules.jobs.models import JobEvent, JobEventType, JobStatus
from oscar_api.modules.jobs.service import get_job_or_404
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
    sections = validate_sections(session, sections)
    # Every CV writer uses the parent job as its first lock. Generations and
    # edits can then allocate from the same monotonically increasing sequence.
    get_job_or_404(session, original.job_id, for_update=True)
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
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Could not save this CV version; retry the edit") from exc
    except Exception:
        session.rollback()
        raise
    session.refresh(new_version)
    return new_version


def validate_sections(session: Session, sections: dict[str, Any]) -> dict[str, Any]:
    """Manual edits and older versions must satisfy the same rules as generation.

    Rebuild presentation metadata server-side; a client cannot forge a source
    snapshot or change the employer printed above a genuine bullet.
    """
    try:
        draft = CVDraft.model_validate(sections)
    except ValidationError as exc:
        raise ValidationFailedError("CV sections do not match the expected structure") from exc
    profile = get_profile(session)
    facts = [a for a in profile.achievements if a.deleted_at is None]
    cleaned, report = verify_draft(draft, GroundingContext.build(profile, facts))
    if report.claims_rejected:
        raise ValidationFailedError(
            "Update the career facts first: this CV contains unsupported claims or skills",
            detail={"grounding_report": report.model_dump()},
        )
    if not (
        cleaned.summary.text
        or any(b.bullets for b in cleaned.experience)
        or any(b.bullets for b in cleaned.projects)
    ):
        raise ValidationFailedError("A CV must contain at least one supported statement")
    return snapshot_sections(cleaned, profile)


def is_approved(session: Session, version: CVVersion) -> bool:
    return (
        session.scalar(
            select(JobEvent.id)
            .where(
                JobEvent.job_id == version.job_id,
                JobEvent.event_type == JobEventType.CV_APPROVED.value,
                JobEvent.event_metadata.contains({"cv_version_id": version.id}),
            )
            .limit(1)
        )
        is not None
    )


def approve_version(session: Session, cv_version_id: int) -> CVVersion:
    version = get_version_or_404(session, cv_version_id)
    job = get_job_or_404(session, version.job_id, for_update=True)
    try:
        validate_sections(session, version.sections)
        if not is_approved(session, version):
            # The locked, refreshed status includes any concurrent application.
            if job.current_status == JobStatus.SAVED:
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
    except Exception:
        session.rollback()
        raise
    session.refresh(version)
    return version


def export_version(session: Session, storage: Storage, cv_version_id: int) -> CVArtifact:
    version = get_version_or_404(session, cv_version_id)
    if not is_approved(session, version):
        raise ConflictError("Review and approve this CV version before exporting it")
    existing = session.scalar(
        select(CVArtifact)
        .where(CVArtifact.cv_version_id == version.id, CVArtifact.kind == "pdf")
        .order_by(CVArtifact.id.desc())
        .limit(1)
    )
    if existing is not None:
        try:
            storage.load(existing.storage_uri)
        except (OSError, KeyError):
            pass  # Missing files can be regenerated after validating current facts below.
        else:
            return existing  # Keep the exact bytes, even if the profile changed later.
    validate_sections(session, version.sections)
    candidate = version.sections.get("candidate") or {}
    if not candidate.get("name") or not candidate.get("email"):
        raise ValidationFailedError(
            "Add your CV name and email in Career Profile, then save a new CV version"
        )

    try:
        pdf_bytes = render_pdf(version)
        uri = storage.save(relative_path=f"cv/{version.label}.pdf", data=pdf_bytes)
    except (FPDFException, OSError) as exc:
        raise StorageError("Could not render or save the PDF; the CV version is unchanged") from exc

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


def download_artifact(
    session: Session, storage: Storage, cv_version_id: int, artifact_id: int
) -> tuple[bytes, str]:
    version = get_version_or_404(session, cv_version_id)
    artifact = session.get(CVArtifact, artifact_id)
    if artifact is None or artifact.cv_version_id != version.id or artifact.kind != "pdf":
        raise NotFoundError("PDF artifact not found for this CV version")
    try:
        return storage.load(artifact.storage_uri), f"{version.label}.pdf"
    except (OSError, KeyError) as exc:
        raise StorageError("The saved PDF is unavailable; try exporting the CV again") from exc


def mark_submitted(session: Session, cv_version_id: int) -> CVVersion:
    version = get_version_or_404(session, cv_version_id)
    get_job_or_404(session, version.job_id, for_update=True)
    try:
        recorded = session.scalars(
            select(Application.submitted_cv_version_id).where(Application.job_id == version.job_id)
        ).all()
        if recorded and any(recorded_id != version.id for recorded_id in recorded):
            raise ConflictError(
                "This application's submitted CV is already recorded; it cannot be changed"
            )
        # Before an application exists this is a manual submission marker. Once
        # one exists, only its recorded CV may be marked; history stays immutable.
        session.execute(
            update(CVVersion).where(CVVersion.job_id == version.job_id).values(is_submitted=False)
        )
        session.execute(
            update(CVVersion).where(CVVersion.id == version.id).values(is_submitted=True)
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Could not mark this CV version as submitted") from exc
    except Exception:
        session.rollback()
        raise
    session.refresh(version)
    return version
