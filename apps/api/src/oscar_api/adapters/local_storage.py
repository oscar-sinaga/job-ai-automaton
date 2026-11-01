"""Local filesystem implementation of the `Storage` port (docs/14 §7)."""

from __future__ import annotations

from pathlib import Path

from oscar_api.config import get_settings

_URI_PREFIX = "file://"


class LocalFileStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or get_settings().storage_dir

    def save(self, *, relative_path: str, data: bytes) -> str:
        target = self._base_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"{_URI_PREFIX}{relative_path}"

    def load(self, uri: str) -> bytes:
        if not uri.startswith(_URI_PREFIX):
            raise ValueError(f"Unsupported storage URI: {uri}")
        relative_path = uri.removeprefix(_URI_PREFIX)
        return (self._base_dir / relative_path).read_bytes()
