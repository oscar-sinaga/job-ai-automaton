"""Pydantic schemas for the applications module (docs/05_API_DESIGN.md §6)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field

from oscar_api.modules.jobs.models import JobStatus


class ApplicationCreate(BaseModel):
    job_id: int
    submitted_cv_version_id: int | None = None


class ApplicationOut(BaseModel):
    id: int
    job_id: int
    submitted_cv_version_id: int | None
    current_status: JobStatus
    created_at: dt.datetime


class ApplicationEventIn(BaseModel):
    event_type: str
    occurred_at: dt.datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationEventOut(BaseModel):
    event_id: int
    current_status: JobStatus


class ApplicationDetail(BaseModel):
    id: int
    job_id: int
    submitted_cv_version_id: int | None
    current_status: JobStatus
    created_at: dt.datetime
    events: list[dict[str, Any]]


class ApplicationAnswerIn(BaseModel):
    question_key: str
    question_text: str | None = None
    answer_text: str
    is_private: bool = False
    source: str = "manual"


class ApplicationAnswerOut(ApplicationAnswerIn):
    id: int
