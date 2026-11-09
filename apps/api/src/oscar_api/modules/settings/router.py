"""Authenticated owner settings; credentials are never returned to a browser."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from oscar_api.config import get_settings
from oscar_api.core.auth import require_api_key
from oscar_api.core.errors import ConflictError
from oscar_api.db import check_database, get_session
from oscar_api.modules.cv.deps import get_storage
from oscar_api.modules.settings.cleanup import drain_file_deletions
from oscar_api.modules.settings.deletion import delete_data, preview_deletion
from oscar_api.modules.settings.exporting import create_export
from oscar_api.modules.settings.preferences import (
    effective_integration,
    read_settings,
    save_integrations,
    save_preferences,
)
from oscar_api.modules.settings.schemas import (
    DeleteDataRequest,
    DeleteDataResult,
    DeletionPreview,
    DeletionPreviewRequest,
    IntegrationOut,
    IntegrationPreferences,
    SettingsOut,
    SettingsUpdate,
)
from oscar_api.ports.storage import Storage

router = APIRouter(tags=["settings"], dependencies=[Depends(require_api_key)])


@router.get("/settings", response_model=SettingsOut)
def settings(session: Session = Depends(get_session)) -> SettingsOut:
    return read_settings(session)


@router.put("/settings", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)) -> SettingsOut:
    return save_preferences(session, body.default_cv_preferences)


@router.get("/settings/integrations", response_model=IntegrationOut)
def integrations(session: Session = Depends(get_session)) -> IntegrationOut:
    config = get_settings()
    model, max_tokens = effective_integration(session)
    return IntegrationOut(
        database_connected=check_database(),
        provider_key_configured=bool(config.openai_api_key),
        cv_model=model,
        max_output_tokens=max_tokens,
        api_key_configured=bool(config.api_key),
        timezone=config.timezone,
    )


@router.put("/settings/integrations", response_model=SettingsOut)
def update_integrations(
    body: IntegrationPreferences,
    session: Session = Depends(get_session),
) -> SettingsOut:
    return save_integrations(session, body)


@router.get("/export", response_class=FileResponse)
def export_data(
    format: Literal["json", "zip"] = Query(default="json"),
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> FileResponse:
    result = create_export(session, storage, format)
    return FileResponse(
        result.path,
        media_type=result.media_type,
        filename=result.filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        background=BackgroundTask(result.path.unlink, missing_ok=True),
    )


@router.post("/settings/data/preview", response_model=DeletionPreview)
def deletion_preview(
    body: DeletionPreviewRequest, session: Session = Depends(get_session)
) -> DeletionPreview:
    return preview_deletion(session, body.scope)


@router.post("/settings/data/delete", response_model=DeleteDataResult)
def delete_owner_data(
    body: DeleteDataRequest,
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> DeleteDataResult:
    try:
        return delete_data(session, storage, body)
    except OperationalError as exc:
        session.rollback()
        raise ConflictError(
            "The workspace is busy. Let active operations finish, then try again."
        ) from exc


@router.post("/settings/files/retry")
def retry_file_cleanup(
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> dict[str, int]:
    deleted, pending = drain_file_deletions(session, storage)
    return {"files_deleted": deleted, "pending_file_deletions": pending}
