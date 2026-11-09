"""Bounded-memory portable data/PDF exports from a consistent database snapshot."""

from __future__ import annotations

import datetime as dt
import enum
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import IO, Any, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from oscar_api.config import get_settings
from oscar_api.core.errors import StorageError
from oscar_api.db import Base
from oscar_api.modules.cv.models import CVArtifact, CVVersion
from oscar_api.modules.settings.deletion import DATA_MAINTENANCE_LOCK
from oscar_api.ports.storage import Storage


@dataclass(frozen=True)
class DataExport:
    path: Path
    media_type: str
    filename: str


def _json_default(value: Any) -> str:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return str(value.value)
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    raise TypeError("Unsupported export value")


def _encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, default=_json_default, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _export_root() -> Path:
    storage_root = get_settings().storage_dir.resolve()
    root = storage_root / ".exports"
    if root.resolve() != root:
        raise StorageError("Export storage is not a safe application directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(root).free < 256 * 1024**2:
        raise StorageError("Not enough free space for a data export; try again after freeing space")
    return root


def _write_dataset(session: Session, stream: IO[bytes]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    checksum = hashlib.sha256()

    def write(value: bytes) -> None:
        stream.write(value)
        checksum.update(value)

    write(b'{"format_version":1,"exported_at":')
    write(_encoded(dt.datetime.now(dt.UTC)))
    write(b',"tables":{')
    first_table = True
    for table in Base.metadata.sorted_tables:
        if table.name == "pending_file_deletions":
            continue
        if not first_table:
            write(b",")
        first_table = False
        write(_encoded(table.name) + b":[")
        # Never export operational deletion-token hashes or pending challenges.
        query = (
            select(
                table.c.user_id,
                table.c.default_cv_preferences,
                table.c.integration_preferences,
                table.c.updated_at,
            )
            if table.name == "user_settings"
            else select(table)
        )
        count = 0
        result = session.execute(query.execution_options(yield_per=20)).mappings()
        try:
            for row in result:
                if count:
                    write(b",")
                write(_encoded(dict(row)))
                count += 1
        finally:
            result.close()
        counts[table.name] = count
        write(b"]")
    write(b'},"manifest":')
    write(_encoded({"rows": counts, "server_credentials_included": False}))
    write(b"}")
    return {"rows": counts, "data_sha256": checksum.hexdigest()}


def create_export(session: Session, storage: Storage, format: Literal["json", "zip"]) -> DataExport:
    root = _export_root()
    fd, raw_path = tempfile.mkstemp(prefix="export-", suffix="." + format, dir=root)
    os.close(fd)
    path = Path(raw_path)
    try:
        session.execute(text("SET LOCAL lock_timeout = '5s'"))
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": DATA_MAINTENANCE_LOCK})
        # Block writers only while the archive is built. The completed file is
        # streamed after releasing locks, so slow downloads do not hold the DB.
        tables = [t for t in Base.metadata.sorted_tables if t.name != "pending_file_deletions"]
        for table in tables:
            session.execute(text(f'LOCK TABLE "{table.name}" IN SHARE MODE'))
        if format == "json":
            with path.open("wb") as output:
                _write_dataset(session, output)
        else:
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                with archive.open("data.json", "w", force_zip64=True) as output:
                    manifest = _write_dataset(session, output)
                files: list[dict[str, Any]] = []
                artifacts = session.execute(
                    select(CVArtifact, CVVersion)
                    .join(CVVersion)
                    .order_by(CVArtifact.id)
                    .execution_options(yield_per=20)
                )
                try:
                    for artifact, version in artifacts:
                        if len(files) >= 10000:
                            raise StorageError(
                                "ZIP export supports up to 10,000 PDFs; "
                                "use JSON for larger metadata exports"
                            )
                        name = f"cv/{version.label}_artifact_{artifact.id}.pdf"
                        size = 0
                        digest = hashlib.sha256()
                        with archive.open(name, "w", force_zip64=True) as output:
                            for chunk in storage.iter_load(artifact.storage_uri):
                                output.write(chunk)
                                digest.update(chunk)
                                size += len(chunk)
                        files.append(
                            {
                                "artifact_id": artifact.id,
                                "file": name,
                                "bytes": size,
                                "sha256": digest.hexdigest(),
                            }
                        )
                finally:
                    artifacts.close()
                manifest.update(
                    {
                        "format_version": 1,
                        "files": files,
                        "credentials_included": False,
                        "note": "Operational cleanup state and server credentials are excluded.",
                    }
                )
                archive.writestr("manifest.json", _encoded(manifest))
        session.commit()
    except Exception as exc:
        session.rollback()
        path.unlink(missing_ok=True)
        if isinstance(exc, StorageError):
            raise
        raise StorageError(
            "Export could not be completed. Check available storage and missing PDF artifacts; "
            "no partial download was created."
        ) from exc
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    return DataExport(
        path=path,
        media_type="application/zip" if format == "zip" else "application/json",
        filename=f"oscar-job-copilot-{stamp}.{format}",
    )


def clean_expired_exports() -> None:
    """Recover abandoned downloads without touching CVs, backups, or other apps."""
    root = get_settings().storage_dir.resolve() / ".exports"
    if not root.is_dir() or root.resolve() != root:
        return
    cutoff = dt.datetime.now(dt.UTC).timestamp() - 3600
    for path in root.iterdir():
        if (
            path.name.startswith("export-")
            and path.suffix in {".json", ".zip"}
            and not path.is_symlink()
            and path.is_file()
            and path.stat().st_mtime < cutoff
        ):
            path.unlink(missing_ok=True)
