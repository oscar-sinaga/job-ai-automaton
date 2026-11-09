"""Retry a committed artifact-deletion outbox, never deleting directories."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from oscar_api.modules.settings.models import PendingFileDeletion
from oscar_api.ports.storage import Storage

logger = logging.getLogger(__name__)


def drain_file_deletions(session: Session, storage: Storage, limit: int = 100) -> tuple[int, int]:
    rows = session.scalars(
        select(PendingFileDeletion)
        .order_by(PendingFileDeletion.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    removed = 0
    for row in rows:
        try:
            storage.delete(row.storage_uri)
        except (OSError, ValueError, KeyError):
            # No path, CV content, or user identifiers in operational logs.
            logger.warning("artifact_cleanup_pending", extra={"cleanup_id": row.id})
        else:
            session.delete(row)
            removed += 1
    session.commit()
    pending = session.scalar(select(func.count()).select_from(PendingFileDeletion)) or 0
    return removed, pending
