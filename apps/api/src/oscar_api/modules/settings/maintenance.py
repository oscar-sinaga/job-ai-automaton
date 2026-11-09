"""Recover interrupted artifact cleanups and abandoned temporary downloads."""

from __future__ import annotations

import logging
import threading

from oscar_api.db import SessionLocal
from oscar_api.modules.settings.cleanup import drain_file_deletions
from oscar_api.modules.settings.exporting import clean_expired_exports
from oscar_api.ports.storage import Storage

logger = logging.getLogger(__name__)


def cleanup_loop(stop: threading.Event, storage: Storage) -> None:
    while not stop.is_set():
        try:
            with SessionLocal() as session:
                drain_file_deletions(session, storage)
            clean_expired_exports()
        except Exception:
            # Retry next minute; never log raw storage paths, SQL, or credentials.
            logger.warning("settings_cleanup_retry_pending")
        stop.wait(60)
