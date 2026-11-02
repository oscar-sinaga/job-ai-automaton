"""Pydantic schemas for the CV module.

`CVDraft` is the LLM's structured-output contract (docs/06 §3): the model may
only select/reorder/reword facts it was given, and every bullet must cite the
fact IDs it draws from. Nothing here trusts that citation without verification
-- see `grounding.py`.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field


class DraftBullet(BaseModel):
    text: str
    supporting_fact_ids: list[str] = Field(default_factory=list)


class DraftExperienceBlock(BaseModel):
    experience_id: int
    bullets: list[DraftBullet] = Field(default_factory=list)


class DraftProjectBlock(BaseModel):
    project_id: int
    bullets: list[DraftBullet] = Field(default_factory=list)


class CVDraft(BaseModel):
    """The LLM's raw output -- verified before anything here is trusted."""

    summary: DraftBullet
    experience: list[DraftExperienceBlock] = Field(default_factory=list)
    projects: list[DraftProjectBlock] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class GroundingRejection(BaseModel):
    text: str
    reason: str


class GroundingReport(BaseModel):
    claims_checked: int
    claims_rejected: int
    rejections: list[GroundingRejection] = Field(default_factory=list)


class GenerateCVRequest(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)
    regenerate_section: str | None = None


class CVGenerationRunOut(BaseModel):
    model_name: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class GenerateCVResponse(BaseModel):
    cv_version_id: int
    label: str
    sections: dict[str, Any]
    missing_requirements: list[str]
    grounding_report: GroundingReport
    run: CVGenerationRunOut


class CVVersionSummary(BaseModel):
    id: int
    version_number: int
    is_submitted: bool
    created_at: dt.datetime


class CVVersionOut(BaseModel):
    id: int
    job_id: int
    version_number: int
    label: str
    summary_text: str | None
    sections: dict[str, Any]
    is_submitted: bool
    is_approved: bool
    created_at: dt.datetime


class CVEditRequest(BaseModel):
    sections: dict[str, Any]


class CVExportResponse(BaseModel):
    artifact_id: int
    storage_uri: str
    download_url: str
