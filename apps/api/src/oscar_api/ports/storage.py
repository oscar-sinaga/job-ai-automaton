"""The file storage port (docs/03_SYSTEM_ARCHITECTURE.md §5).

Filesystem today (`adapters/local_storage.py`); swapping to S3-compatible
storage later touches only the adapter, never a caller.
"""

from __future__ import annotations

from typing import Protocol


class Storage(Protocol):
    def save(self, *, relative_path: str, data: bytes) -> str:
        """Persist `data`; return a URI callers store and pass back to `load`."""
        ...

    def load(self, uri: str) -> bytes: ...
