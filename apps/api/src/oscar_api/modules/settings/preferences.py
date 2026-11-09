"""Validated defaults, deliberately separate from provider credentials."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from oscar_api.config import get_settings
from oscar_api.core.errors import ValidationFailedError
from oscar_api.core.models import SINGLE_USER_ID
from oscar_api.modules.settings.models import PendingFileDeletion, UserSettings
from oscar_api.modules.settings.schemas import CVPreferences, IntegrationPreferences, SettingsOut


def locked_settings(session: Session) -> UserSettings:
    session.execute(
        insert(UserSettings)
        .values(user_id=SINGLE_USER_ID, default_cv_preferences={}, integration_preferences={})
        .on_conflict_do_nothing(index_elements=[UserSettings.user_id])
    )
    return session.scalars(
        select(UserSettings)
        .where(UserSettings.user_id == SINGLE_USER_ID)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def read_settings(session: Session) -> SettingsOut:
    row = session.get(UserSettings, SINGLE_USER_ID)
    return SettingsOut(
        default_cv_preferences=CVPreferences.model_validate(
            row.default_cv_preferences if row else {}
        ),
        updated_at=row.updated_at if row else None,
        pending_file_deletions=session.scalar(select(func.count()).select_from(PendingFileDeletion))
        or 0,
        integration_preferences=IntegrationPreferences.model_validate(
            row.integration_preferences if row else {}
        ),
    )


def save_preferences(session: Session, preferences: CVPreferences) -> SettingsOut:
    row = locked_settings(session)
    row.default_cv_preferences = preferences.model_dump()
    row.updated_at = dt.datetime.now(dt.UTC)
    session.commit()
    session.refresh(row)
    return read_settings(session)


def effective_preferences(session: Session, overrides: dict[str, Any]) -> CVPreferences:
    saved = read_settings(session).default_cv_preferences.model_dump()
    try:
        return CVPreferences.model_validate(saved | overrides)
    except ValidationError as exc:
        raise ValidationFailedError(
            "CV preferences are invalid; review Settings or this request"
        ) from exc


def effective_integration(session: Session) -> tuple[str, int]:
    preferences = read_settings(session).integration_preferences
    config = get_settings()
    return (
        preferences.model or config.llm_model,
        preferences.max_output_tokens or config.llm_max_output_tokens,
    )


def save_integrations(session: Session, preferences: IntegrationPreferences) -> SettingsOut:
    row = locked_settings(session)
    row.integration_preferences = preferences.model_dump()
    row.updated_at = dt.datetime.now(dt.UTC)
    session.commit()
    session.refresh(row)
    return read_settings(session)
