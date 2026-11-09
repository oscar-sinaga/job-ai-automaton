"""Explicit, replay-resistant deletion of this single-owner application's data.

No DROP, TRUNCATE, identity reset, database replacement, or cross-app file removal.
The preview token is single-use; a changed row count requires a fresh preview.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import logging
import secrets

from sqlalchemy import Table, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from oscar_api.core.errors import ConflictError, ValidationFailedError
from oscar_api.core.models import SINGLE_USER_ID
from oscar_api.db import Base
from oscar_api.modules.career.models import ApplicationProfile, CareerProfile
from oscar_api.modules.cv.models import CVArtifact
from oscar_api.modules.jobs.models import Job
from oscar_api.modules.settings.cleanup import drain_file_deletions
from oscar_api.modules.settings.models import PendingFileDeletion
from oscar_api.modules.settings.preferences import locked_settings
from oscar_api.modules.settings.schemas import (
    DeleteDataRequest,
    DeleteDataResult,
    DeletionPreview,
    DeletionScope,
)
from oscar_api.ports.storage import Storage

# Export and reset coordinate through this transaction-scoped advisory lock.
DATA_MAINTENANCE_LOCK = 731022410
_PRESERVED = {"users", "user_settings", "pending_file_deletions", "role_categories"}
logger = logging.getLogger(__name__)


def data_tables(scope: DeletionScope) -> list[Table]:
    tables = [t for t in Base.metadata.sorted_tables if t.name not in _PRESERVED]
    if scope == "all":
        return tables
    related = {"jobs"}
    while True:
        added = {
            t.name for t in tables if any(fk.column.table.name in related for fk in t.foreign_keys)
        }
        if added <= related:
            break
        related |= added
    return [t for t in tables if t.name in related]


def row_counts(session: Session, scope: DeletionScope) -> dict[str, int]:
    return {
        t.name: session.scalar(select(func.count()).select_from(t)) or 0 for t in data_tables(scope)
    }


def confirmation_phrase(scope: DeletionScope) -> str:
    return "DELETE MY JOBS" if scope == "jobs" else "DELETE ALL MY DATA"


def preview_deletion(session: Session, scope: DeletionScope) -> DeletionPreview:
    row = locked_settings(session)
    token = secrets.token_urlsafe(32)
    expires = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5)
    counts = row_counts(session, scope)
    row.deletion_token_hash = hashlib.sha256(token.encode()).hexdigest()
    row.deletion_scope = scope
    row.deletion_expires_at = expires
    row.deletion_counts = counts
    session.commit()
    return DeletionPreview(
        scope=scope,
        counts=counts,
        token=token,
        expires_at=expires,
        confirmation_phrase=confirmation_phrase(scope),
    )


def delete_data(session: Session, storage: Storage, request: DeleteDataRequest) -> DeleteDataResult:
    if request.confirmation != confirmation_phrase(request.scope):
        raise ValidationFailedError("Type the exact confirmation phrase before deleting data")
    # Lock order is fixed: maintenance gate, settings row, FK-ordered data tables.
    session.execute(text("SET LOCAL lock_timeout = '5s'"))
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": DATA_MAINTENANCE_LOCK})
    row = locked_settings(session)
    if (
        not row.deletion_token_hash
        or row.deletion_scope != request.scope
        or not row.deletion_expires_at
        or row.deletion_expires_at <= dt.datetime.now(dt.UTC)
        or not hmac.compare_digest(
            row.deletion_token_hash, hashlib.sha256(request.token.encode()).hexdigest()
        )
    ):
        raise ConflictError("Deletion preview expired or was already used; review the data again")
    tables = data_tables(request.scope)
    # Block concurrent inserts/updates while capturing artifact URIs and deleting
    # dependent rows. Names come exclusively from trusted SQLAlchemy metadata.
    for table in tables:
        session.execute(text(f'LOCK TABLE "{table.name}" IN EXCLUSIVE MODE'))
    counts = row_counts(session, request.scope)
    if counts != row.deletion_counts:
        raise ConflictError("Your data changed after the preview; review it again before deleting")
    uris = session.scalars(select(CVArtifact.storage_uri)).all()
    for uri in set(uris):
        session.execute(
            insert(PendingFileDeletion)
            .values(storage_uri=uri)
            .on_conflict_do_nothing(index_elements=[PendingFileDeletion.storage_uri])
        )
    # The self-reference otherwise blocks a root job when duplicates point to it.
    session.execute(update(Job).values(duplicate_of_job_id=None))
    for table in reversed(tables):
        session.execute(delete(table))
    if request.scope == "all":
        # Preserve a usable empty profile and implicit account, not career facts.
        profile_id = session.execute(
            insert(CareerProfile)
            .values(user_id=SINGLE_USER_ID, summary=None)
            .returning(CareerProfile.id)
        ).scalar_one()
        session.execute(insert(ApplicationProfile).values(profile_id=profile_id, links={}))
        row.default_cv_preferences = {}
        row.integration_preferences = {}
        row.updated_at = dt.datetime.now(dt.UTC)
    row.deletion_token_hash = None
    row.deletion_scope = None
    row.deletion_expires_at = None
    row.deletion_counts = None
    queued = session.scalar(select(func.count()).select_from(PendingFileDeletion)) or 0
    session.commit()
    # A failed filesystem delete stays queued for the worker; DB rollback can
    # never leave a pre-commit file unlink. Retry is safe if a file is missing.
    try:
        deleted, pending = drain_file_deletions(session, storage)
    except SQLAlchemyError:
        # The deletion already committed. A later cleanup/database outage must
        # not tell the owner it failed or encourage replaying the consumed token.
        session.rollback()
        logger.warning("artifact_cleanup_deferred_after_reset")
        deleted, pending = 0, queued
    return DeleteDataResult(
        scope=request.scope,
        deleted_rows=counts,
        files_deleted=deleted,
        pending_file_deletions=pending,
    )
