from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DeletionScope = Literal["jobs", "all"]


class CVPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Literal["en", "id"] = "en"
    layout: Literal["standard", "compact"] = "standard"
    max_bullets_per_role: int = Field(default=5, ge=1, le=8, strict=True)


class IntegrationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,99}$")
    max_output_tokens: int | None = Field(default=None, ge=512, le=16000, strict=True)

    @field_validator("model")
    @classmethod
    def reject_credential_in_model(cls, value: str | None) -> str | None:
        if value and value.startswith("sk-"):
            raise ValueError("Enter a model ID rather than a provider credential")
        return value


class SettingsOut(BaseModel):
    default_cv_preferences: CVPreferences
    integration_preferences: IntegrationPreferences
    updated_at: dt.datetime | None
    pending_file_deletions: int = 0


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_cv_preferences: CVPreferences


class IntegrationOut(BaseModel):
    backend: Literal["online"] = "online"
    database_connected: bool
    provider: Literal["OpenAI"] = "OpenAI"
    provider_key_configured: bool
    cv_model: str
    max_output_tokens: int
    api_key_configured: bool
    timezone: str


class DeletionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: DeletionScope


class DeletionPreview(BaseModel):
    scope: DeletionScope
    counts: dict[str, int]
    confirmation_phrase: str
    token: str
    expires_at: dt.datetime


class DeleteDataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: DeletionScope
    confirmation: str = Field(min_length=1, max_length=64)
    token: str = Field(min_length=32, max_length=128)


class DeleteDataResult(BaseModel):
    scope: DeletionScope
    deleted_rows: dict[str, int]
    files_deleted: int
    pending_file_deletions: int
