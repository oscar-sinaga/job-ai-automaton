"""Local filesystem implementation of the `Storage` port (docs/14 §7)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from oscar_api.config import get_settings

_URI_PREFIX = "file://"


class LocalFileStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or get_settings().storage_dir

    def save(self, *, relative_path: str, data: bytes) -> str:
        target = self._target(f"{_URI_PREFIX}{relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"{_URI_PREFIX}{relative_path}"

    def load(self, uri: str) -> bytes:
        return self._target(uri).read_bytes()

    def iter_load(self, uri: str) -> Iterator[bytes]:
        with self._target(uri).open("rb") as source:
            while chunk := source.read(256 * 1024):
                yield chunk

    def delete(self, uri: str) -> None:
        self._target(uri).unlink(missing_ok=True)

    def _target(self, uri: str) -> Path:
        if not uri.startswith(_URI_PREFIX):
            raise ValueError("Unsupported storage URI")
        relative_path = uri.removeprefix(_URI_PREFIX)
        parts = PurePosixPath(relative_path)
        if not relative_path or parts.is_absolute() or ".." in parts.parts or "\\" in relative_path:
            raise ValueError("Artifact path must stay within application storage")
        root = self._base_dir.resolve()
        target = (root / relative_path).resolve()
        if target == root or not target.is_relative_to(root):
            raise ValueError("Artifact path must stay within application storage")
        return target
