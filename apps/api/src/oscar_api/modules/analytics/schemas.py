"""Pydantic schemas for the analytics module (docs/05_API_DESIGN.md §8)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field

# FR-010 standing disclosure -- shown on every analytics response, not just
# the dashboard, since any of these endpoints could be viewed on its own.
SAMPLE_NOTE = "Analytics describe your captured-job sample, not the job market."


class KPIs(BaseModel):
    saved: int
    ready_to_apply: int
    applied: int
    assessment: int
    interview: int
    final_interview: int
    offer: int
    rejected: int


class FunnelStage(BaseModel):
    stage: str
    count: int


class Conversion(BaseModel):
    applied_over_saved: float | None
    assessment_over_applied: float | None
    interview_over_applied: float | None
    offer_over_interview: float | None
    offer_over_applied: float | None


class Backlog(BaseModel):
    cv_ready_not_applied: int
    saved_older_than_5d: int
    jobs_without_cv: int
    applications_needing_action: int
    partial_captures: int


class ActionQueueItem(BaseModel):
    label: str
    count: int
    href: str


class DashboardOut(BaseModel):
    kpis: KPIs
    funnel: list[FunnelStage]
    conversion: Conversion
    backlog: Backlog
    action_queue: list[ActionQueueItem]
    sample_note: str = SAMPLE_NOTE


class TrendPoint(BaseModel):
    bucket: dt.datetime
    saved: int
    applied: int
    interviews: int
    offers: int


class SourceStat(BaseModel):
    name: str
    saved: int
    applied: int
    interview: int
    applied_rate: float | None


class RoleStat(BaseModel):
    name: str
    saved: int
    applied: int
    interview: int
    applied_rate: float | None


class SkillAnalyticsOut(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    note: str = (
        "Skill analytics require job_skills data, populated by the job_parser "
        "agent (P1, not yet built) -- see docs/15_ROADMAP_AND_MILESTONES.md."
    )


class ProductivityOut(BaseModel):
    median_saved_to_cv_ready_days: float | None
    median_saved_to_applied_days: float | None
    applications_last_7d: int
    backlog_size: int
