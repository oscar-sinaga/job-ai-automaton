"""Stream a backup of the configured PDF directory to stdout."""

from __future__ import annotations

import sys
import tarfile

from oscar_api.config import get_settings

storage = get_settings().storage_dir
storage.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add(storage, arcname="pdfs")
