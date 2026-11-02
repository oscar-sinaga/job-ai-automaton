"""Pydantic request/response schemas for the jobs module (docs/05_API_DESIGN.md)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from oscar_api.modules.jobs.models import CaptureCompleteness, CaptureMethod, JobStatus


class CaptureEnvelope(BaseModel):
    """The one shared capture contract for extension, mobile share, and web
    fallbacks (docs/08 §2). Deliberately has no `capture_completeness` field --
    the server derives it (ADR-012)."""

    url: str
    captured_at: dt.datetime
    capture_method: CaptureMethod
    source_hint: str | None = None
    page_title: str | None = None
    job_title: str | None = Field(default=None, max_length=500)
    company_name: str | None = Field(default=None, max_length=500)
    raw_text: str | None = None
    selected_text: str | None = None
    shared_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SnapshotEnrichment(BaseModel):
    raw_text: str | None = None
    capture_method: CaptureMethod
    captured_at: dt.datetime


class CaptureResponse(BaseModel):
    job_id: int
    ref: str
    capture_completeness: CaptureCompleteness
    duplicate_of_job_id: int | None
    snapshot_id: int
    created: bool  # False when an Idempotency-Key replay returned the original job


class SnapshotEnrichmentResponse(BaseModel):
    snapshot_id: int
    capture_completeness: CaptureCompleteness


class RawSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    raw_text: str | None


class SnapshotMeta(BaseModel):
    """Metadata only -- bodies are large, fetched separately (docs/05 §4)."""

    id: int
    capture_method: CaptureMethod
    captured_at: dt.datetime
    raw_text_length: int
    page_title: str | None


class JobEventOut(BaseModel):
    event_type: str
    actor: str
    metadata: dict[str, Any]
    occurred_at: dt.datetime


class JobSummary(BaseModel):
    id: int
    ref: str
    title: str | None
    company: str | None
    source: str | None
    current_status: JobStatus
    capture_completeness: CaptureCompleteness
    # CV features arrive in M3; kept in the contract now so the inbox UI and
    # this schema don't need a breaking change later.
    cv_ready: bool = False
    latest_cv_version: int | None = None
    created_at: dt.datetime
    is_duplicate: bool


class JobList(BaseModel):
    items: list[JobSummary]
    next_cursor: str | None


class JobDetail(BaseModel):
    id: int
    ref: str
    title: str | None
    company: str | None
    source: str | None
    url: str
    canonical_url: str | None
    capture_completeness: CaptureCompleteness
    current_status: JobStatus
    duplicate_of_job_id: int | None
    created_at: dt.datetime
    updated_at: dt.datetime
    snapshots: list[SnapshotMeta]
    events: list[JobEventOut]


class JobPatch(BaseModel):
    """Manual corrections (docs/05 §4). Location/parsed-field overrides arrive
    with job_parsed_data in M3; only title/company are correctable in M1."""

    title: str | None = None
    company: str | None = None
