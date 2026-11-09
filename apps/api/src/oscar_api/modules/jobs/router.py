"""HTTP surface for the jobs module (docs/05_API_DESIGN.md §3-4)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from oscar_api.core.auth import require_api_key
from oscar_api.core.errors import ValidationFailedError
from oscar_api.db import get_session
from oscar_api.modules.jobs import service
from oscar_api.modules.jobs.models import CaptureCompleteness, Job, JobStatus
from oscar_api.modules.jobs.schemas import (
    CaptureEnvelope,
    CaptureResponse,
    JobDetail,
    JobEventOut,
    JobList,
    JobPatch,
    JobSummary,
    RawSnapshotOut,
    SnapshotEnrichment,
    SnapshotEnrichmentResponse,
    SnapshotMeta,
)

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


def _to_summary(job: Job) -> JobSummary:
    return JobSummary(
        id=job.id,
        ref=job.ref,
        title=job.title,
        company=job.company.name if job.company else None,
        source=job.source.name if job.source else None,
        current_status=job.current_status,
        capture_completeness=job.capture_completeness,
        created_at=job.created_at,
        is_duplicate=job.duplicate_of_job_id is not None,
    )


def _to_detail(job: Job) -> JobDetail:
    return JobDetail(
        id=job.id,
        ref=job.ref,
        title=job.title,
        company=job.company.name if job.company else None,
        source=job.source.name if job.source else None,
        url=job.url,
        canonical_url=job.canonical_url,
        capture_completeness=job.capture_completeness,
        current_status=job.current_status,
        duplicate_of_job_id=job.duplicate_of_job_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        snapshots=[
            SnapshotMeta(
                id=s.id,
                capture_method=s.capture_method,
                captured_at=s.captured_at,
                raw_text_length=len(s.raw_text) if s.raw_text else 0,
                page_title=s.page_title,
            )
            for s in job.snapshots
        ],
        events=[
            JobEventOut(
                event_type=e.event_type,
                actor=e.actor,
                metadata=e.event_metadata,
                occurred_at=e.occurred_at,
            )
            for e in job.events
        ],
    )


@router.post("/capture", response_model=CaptureResponse)
def capture(
    envelope: CaptureEnvelope,
    response: Response,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=64
    ),
) -> CaptureResponse:
    job, snapshot, created = service.capture_job(session, envelope, idempotency_key)
    # A replayed Idempotency-Key returns the original job with 200, not 201
    # (docs/05 §3) -- the request succeeded, but nothing new was created.
    response.status_code = 201 if created else 200
    return CaptureResponse(
        job_id=job.id,
        ref=job.ref,
        capture_completeness=job.capture_completeness,
        duplicate_of_job_id=job.duplicate_of_job_id,
        snapshot_id=snapshot.id,
        created=created,
    )


def _parse_older_than(value: str | None) -> int | None:
    """Accepts "5d" (days) as used by the action-queue hrefs (docs/05 §8)."""
    if value is None:
        return None
    if len(value) > 7 or not re.fullmatch(r"[0-9]+d?", value):
        raise ValidationFailedError("Use an age filter such as 5d (0 to 36500 days)")
    days = int(value.removesuffix("d"))
    if days > 36_500:
        raise ValidationFailedError("Age filter must be between 0 and 36500 days")
    return days


@router.get("", response_model=JobList)
def list_jobs(
    status: JobStatus | None = None,
    source: str | None = None,
    q: str | None = None,
    completeness: CaptureCompleteness | None = None,
    older_than: str | None = None,
    missing_cv: bool = False,
    needs_action: bool = False,
    needs_description: bool = False,
    exclude_duplicates: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, min_length=1, max_length=64),
    session: Session = Depends(get_session),
) -> JobList:
    items, next_cursor = service.list_jobs(
        session,
        status=status,
        source=source,
        q=q,
        completeness=completeness,
        older_than_days=_parse_older_than(older_than),
        missing_cv=missing_cv,
        needs_action=needs_action,
        needs_description=needs_description,
        exclude_duplicates=exclude_duplicates,
        limit=limit,
        cursor=cursor,
    )
    return JobList(items=[_to_summary(job) for job in items], next_cursor=next_cursor)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: int, session: Session = Depends(get_session)) -> JobDetail:
    job = service.get_job_or_404(session, job_id)
    return _to_detail(job)


@router.get("/{job_id}/raw", response_model=RawSnapshotOut)
def get_raw(job_id: int, session: Session = Depends(get_session)) -> RawSnapshotOut:
    snapshot = service.get_latest_raw_snapshot(session, job_id)
    return RawSnapshotOut(snapshot_id=snapshot.id, raw_text=snapshot.raw_text)


@router.patch("/{job_id}", response_model=JobDetail)
def patch_job(job_id: int, patch: JobPatch, session: Session = Depends(get_session)) -> JobDetail:
    job = service.patch_job(session, job_id, patch)
    return _to_detail(job)


@router.post("/{job_id}/snapshots", response_model=SnapshotEnrichmentResponse, status_code=201)
def add_snapshot(
    job_id: int, enrichment: SnapshotEnrichment, session: Session = Depends(get_session)
) -> SnapshotEnrichmentResponse:
    snapshot, completeness = service.add_snapshot(session, job_id, enrichment)
    return SnapshotEnrichmentResponse(snapshot_id=snapshot.id, capture_completeness=completeness)


@router.post("/{job_id}/skip", response_model=JobDetail)
def skip_job(job_id: int, session: Session = Depends(get_session)) -> JobDetail:
    return _to_detail(service.skip_job(session, job_id))


@router.post("/{job_id}/unskip", response_model=JobDetail)
def unskip_job(job_id: int, session: Session = Depends(get_session)) -> JobDetail:
    return _to_detail(service.unskip_job(session, job_id))
