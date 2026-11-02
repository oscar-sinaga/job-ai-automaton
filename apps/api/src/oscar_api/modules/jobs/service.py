"""Jobs module service layer -- the only thing routers call directly.

Every write here is a single, deliberate transaction: capture always produces a
job + raw snapshot + JOB_SAVED event together (docs/03 §3.1), and any status or
field change that matters writes an event in the same transaction. Nothing in
this file imports `openai`, `httpx`, or any adapter -- it is pure domain logic
over SQLAlchemy, which is what makes it unit-testable without a running server.
"""

from __future__ import annotations

import base64
import datetime as dt
import re
from urllib.parse import urlparse

from sqlalchemy import column, exists, func, select, table
from sqlalchemy.orm import Session

from oscar_api.core.errors import IllegalTransitionError, NotFoundError
from oscar_api.core.models import SINGLE_USER_ID
from oscar_api.modules.jobs.dedupe import canonicalize_url, compute_dedupe_key
from oscar_api.modules.jobs.models import (
    CaptureCompleteness,
    CaptureMethod,
    Company,
    Job,
    JobEvent,
    JobEventType,
    JobRawSnapshot,
    JobStatus,
    Source,
    SourceKind,
)
from oscar_api.modules.jobs.schemas import CaptureEnvelope, JobPatch, SnapshotEnrichment

# Below this, text is treated as "not really a JD" (e.g. a stray "N/A") rather
# than a complete capture -- a tunable threshold, not a spec'd constant.
MIN_COMPLETE_TEXT_CHARS = 40

# docs/05 §3: raw_text is capped at 200 KB; longer bodies are truncated rather
# than rejected.
MAX_RAW_TEXT_CHARS = 200_000


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _effective_text(envelope: CaptureEnvelope) -> str | None:
    for candidate in (envelope.raw_text, envelope.selected_text, envelope.shared_text):
        if candidate and candidate.strip():
            return candidate
    return None


def _capped_text(text: str | None) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    if len(text) > MAX_RAW_TEXT_CHARS:
        return text[:MAX_RAW_TEXT_CHARS], True
    return text, False


def derive_capture_completeness(envelope: CaptureEnvelope) -> CaptureCompleteness:
    """Server-derived, never trusted from the client (ADR-012, docs/05 §3)."""
    text = _effective_text(envelope)
    if text and len(text.strip()) >= MIN_COMPLETE_TEXT_CHARS:
        return CaptureCompleteness.CAPTURED_COMPLETE
    if envelope.capture_method == CaptureMethod.manual_url and not text:
        return CaptureCompleteness.NEEDS_ENRICHMENT
    return CaptureCompleteness.CAPTURED_PARTIAL


def resolve_source(session: Session, source_hint: str | None, url: str) -> Source:
    host = (source_hint or urlparse(url).netloc).lower().removeprefix("www.") or "unknown"
    existing = session.execute(select(Source).where(Source.name == host)).scalar_one_or_none()
    if existing:
        return existing
    source = Source(name=host, kind=SourceKind.job_board)
    session.add(source)
    session.flush()
    return source


def resolve_company(session: Session, name: str) -> Company:
    normalized = _slug(name)
    existing = session.execute(
        select(Company).where(Company.normalized_name == normalized)
    ).scalar_one_or_none()
    if existing:
        return existing
    company = Company(name=name, normalized_name=normalized)
    session.add(company)
    session.flush()
    return company


def get_job_or_404(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.user_id != SINGLE_USER_ID:
        raise NotFoundError(f"Job {job_id} not found")
    return job


def capture_job(
    session: Session, envelope: CaptureEnvelope, idempotency_key: str | None
) -> tuple[Job, JobRawSnapshot, bool]:
    """Returns (job, snapshot, created). `created=False` means an
    Idempotency-Key replay returned the original job untouched (ADR-013)."""
    if idempotency_key:
        existing = session.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            latest_snapshot = existing.snapshots[-1]
            return existing, latest_snapshot, False

    completeness = derive_capture_completeness(envelope)
    canonical = canonicalize_url(envelope.url)
    dedupe_key = compute_dedupe_key(envelope.url)

    duplicate = (
        session.execute(
            select(Job).where(Job.dedupe_key == dedupe_key, Job.user_id == SINGLE_USER_ID)
        )
        .scalars()
        .first()
    )
    source = resolve_source(session, envelope.source_hint, envelope.url)
    company_name = (envelope.company_name or "").strip()
    company = resolve_company(session, company_name) if _slug(company_name) else None

    job = Job(
        ref="",  # assigned below once `id` is known
        user_id=SINGLE_USER_ID,
        source_id=source.id,
        company_id=company.id if company else None,
        url=envelope.url,
        canonical_url=canonical,
        title=(envelope.job_title or "").strip() or envelope.page_title,
        capture_completeness=completeness,
        current_status=JobStatus.SAVED,
        dedupe_key=dedupe_key,
        duplicate_of_job_id=duplicate.id if duplicate else None,
        idempotency_key=idempotency_key,
    )
    session.add(job)
    session.flush()
    job.ref = f"J{job.id:03d}"

    raw_text, truncated = _capped_text(_effective_text(envelope))
    raw_metadata: dict[str, object] = dict(envelope.metadata)
    if truncated:
        raw_metadata["truncated"] = True

    snapshot = JobRawSnapshot(
        job_id=job.id,
        raw_text=raw_text,
        page_title=envelope.page_title,
        capture_method=envelope.capture_method,
        raw_metadata=raw_metadata,
        captured_at=envelope.captured_at,
    )
    session.add(snapshot)

    session.add(
        JobEvent(
            job_id=job.id,
            event_type=JobEventType.JOB_SAVED.value,
            actor="user",
            event_metadata={"capture_method": envelope.capture_method.value},
            occurred_at=envelope.captured_at,
        )
    )

    session.commit()
    session.refresh(job)
    session.refresh(snapshot)
    return job, snapshot, True


def add_snapshot(
    session: Session, job_id: int, enrichment: SnapshotEnrichment
) -> tuple[JobRawSnapshot, CaptureCompleteness]:
    job = get_job_or_404(session, job_id)
    raw_text, truncated = _capped_text(enrichment.raw_text)

    snapshot = JobRawSnapshot(
        job_id=job.id,
        raw_text=raw_text,
        page_title=None,
        capture_method=enrichment.capture_method,
        raw_metadata={"truncated": True} if truncated else {},
        captured_at=enrichment.captured_at,
    )
    session.add(snapshot)

    if raw_text and job.capture_completeness != CaptureCompleteness.CAPTURED_COMPLETE:
        job.capture_completeness = CaptureCompleteness.CAPTURED_COMPLETE
        session.add(
            JobEvent(
                job_id=job.id,
                event_type=JobEventType.JOB_UPDATED.value,
                actor="user",
                event_metadata={"reason": "enrichment"},
                occurred_at=enrichment.captured_at,
            )
        )

    session.commit()
    session.refresh(snapshot)
    session.refresh(job)
    return snapshot, job.capture_completeness


def get_latest_raw_snapshot(session: Session, job_id: int) -> JobRawSnapshot:
    job = get_job_or_404(session, job_id)
    if not job.snapshots:
        raise NotFoundError(f"No raw snapshot for job {job_id}")
    return job.snapshots[-1]


def _encode_cursor(job_id: int) -> str:
    return base64.urlsafe_b64encode(str(job_id).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    return int(base64.urlsafe_b64decode(cursor.encode()).decode())


# Referenced by name only (no model import) so these filters don't create a
# Python-level dependency on the cv/applications modules -- jobs stays a
# dependency leaf (docs/03 §2) while still being able to reproduce exactly
# what the analytics action queue counted (docs/05 §8, docs/10 §6).
_cv_versions_table = table("cv_versions", column("job_id"))
_job_timeline_view = table("v_job_timeline", column("job_id"), column("occurred_at"))

_NEEDS_ACTION_STATUSES = (JobStatus.ASSESSMENT, JobStatus.INTERVIEW, JobStatus.FINAL_INTERVIEW)
_MISSING_CV_STATUSES = (JobStatus.SAVED, JobStatus.READY_TO_APPLY)


def list_jobs(
    session: Session,
    *,
    status: JobStatus | None = None,
    source: str | None = None,
    q: str | None = None,
    completeness: CaptureCompleteness | None = None,
    older_than_days: int | None = None,
    missing_cv: bool = False,
    needs_action: bool = False,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[Job], str | None]:
    stmt = select(Job).where(Job.user_id == SINGLE_USER_ID).order_by(Job.id.desc())
    if status is not None:
        stmt = stmt.where(Job.current_status == status)
    if source is not None:
        stmt = stmt.join(Source, Job.source_id == Source.id).where(Source.name == source)
    if q:
        stmt = stmt.where(func.lower(Job.title).like(f"%{q.lower()}%"))
    if completeness is not None:
        # Unlike missing_cv/needs_action below, this stays duplicate-inclusive
        # (consistent with the plain `status` filter) since it's also a
        # plausible general-purpose browsing filter, not backlog-exclusive.
        # The "partial_captures" backlog count itself excludes duplicates
        # (docs/10 D2) -- if that count is ever nonzero with a duplicate
        # present, this link could show one more row than the count. Revisit
        # if real usage (M6) shows this in practice.
        stmt = stmt.where(Job.capture_completeness == completeness)
    if older_than_days is not None:
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=older_than_days)
        stmt = stmt.where(Job.created_at < cutoff)
    if missing_cv:
        # Duplicates are excluded here to match the backlog count exactly
        # (docs/10 D2 -- v_job_stages, which that count is built on, excludes
        # them too); a mismatched count vs. link contents is a bug (docs/12 §4).
        stmt = stmt.where(
            Job.current_status.in_(_MISSING_CV_STATUSES),
            Job.duplicate_of_job_id.is_(None),
            ~exists().where(_cv_versions_table.c.job_id == Job.id),
        )
    if needs_action:
        recent_activity = (
            select(func.max(_job_timeline_view.c.occurred_at))
            .where(_job_timeline_view.c.job_id == Job.id)
            .scalar_subquery()
        )
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=7)
        stmt = stmt.where(
            Job.current_status.in_(_NEEDS_ACTION_STATUSES),
            Job.duplicate_of_job_id.is_(None),
            (recent_activity.is_(None)) | (recent_activity < cutoff),
        )
    if cursor:
        stmt = stmt.where(Job.id < _decode_cursor(cursor))

    rows = list(session.execute(stmt.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1].id) if has_more and items else None
    return items, next_cursor


def patch_job(session: Session, job_id: int, patch: JobPatch) -> Job:
    job = get_job_or_404(session, job_id)
    changed_fields: dict[str, object] = {}

    if patch.title is not None and patch.title != job.title:
        job.title = patch.title
        changed_fields["title"] = patch.title
    if patch.company is not None:
        company = resolve_company(session, patch.company)
        if job.company_id != company.id:
            job.company_id = company.id
            changed_fields["company"] = patch.company

    if changed_fields:
        session.add(
            JobEvent(
                job_id=job.id,
                event_type=JobEventType.JOB_UPDATED.value,
                actor="user",
                event_metadata={"fields": changed_fields},
                occurred_at=dt.datetime.now(dt.UTC),
            )
        )
        session.commit()
        session.refresh(job)
    return job


# ── Pre-application status changes ───────────────────────────────────────────
# SKIPPED/un-skip don't need an Application row (a job can be skipped before
# ever being applied to), so they live here rather than in the applications
# module's state machine, which governs APPLIED-and-beyond transitions.

_SKIPPABLE_STATUSES = (JobStatus.SAVED, JobStatus.READY_TO_APPLY, JobStatus.APPLYING)


def skip_job(session: Session, job_id: int) -> Job:
    job = get_job_or_404(session, job_id)
    if job.current_status not in _SKIPPABLE_STATUSES:
        raise IllegalTransitionError(
            f"Cannot skip a job in status {job.current_status.value}",
            detail={"from": job.current_status.value},
        )
    job.current_status = JobStatus.SKIPPED
    session.add(
        JobEvent(
            job_id=job.id,
            event_type=JobEventType.JOB_UPDATED.value,
            actor="user",
            event_metadata={"reason": "skipped"},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(job)
    return job


def unskip_job(session: Session, job_id: int) -> Job:
    job = get_job_or_404(session, job_id)
    if job.current_status != JobStatus.SKIPPED:
        raise IllegalTransitionError(
            f"Cannot un-skip a job in status {job.current_status.value}",
            detail={"from": job.current_status.value},
        )
    job.current_status = JobStatus.SAVED
    session.add(
        JobEvent(
            job_id=job.id,
            event_type=JobEventType.JOB_UPDATED.value,
            actor="user",
            event_metadata={"reason": "unskipped"},
            occurred_at=dt.datetime.now(dt.UTC),
        )
    )
    session.commit()
    session.refresh(job)
    return job
