"""Manage the local OSCAR pilot with Docker Compose. Requires Python 3.12+."""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import secrets
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def initialize(env_file: Path, simulation: bool) -> None:
    password = secrets.token_urlsafe(32)
    database = "oscar_simulation_pilot" if simulation else "oscar_pilot"
    values = {
        "OSCAR_ENV": "simulation" if simulation else "local",
        "OSCAR_DATABASE_NAME": database,
        "POSTGRES_PASSWORD": password,
        "OSCAR_DATABASE_URL": f"postgresql+psycopg://oscar:{password}@db:5432/{database}",
        "OSCAR_API_KEY": secrets.token_urlsafe(32),
        "OPENAI_API_KEY": "",
    }
    # Exclusive creation preserves any existing credentials and configuration.
    descriptor = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
    print(f"Initialized {env_file.name}. Keep this file private.")


def configure_ai(env_file: Path) -> None:
    """Read a provider key without terminal echo, command arguments or logs."""
    if env_file.is_symlink() or not env_file.is_file():
        raise ValueError("Run init first; the configuration must be a regular file.")
    lines = env_file.read_text().splitlines(keepends=True)
    if sum(line.startswith("OPENAI_API_KEY=") for line in lines) != 1:
        raise ValueError("The configuration must contain exactly one OPENAI_API_KEY entry.")
    key = getpass.getpass("OpenAI API key (hidden): ").strip()
    if not key.startswith("sk-") or len(key) < 30 or any(c in key for c in "\r\n"):
        raise ValueError("The OpenAI API key format is invalid; configuration was not changed.")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=env_file.parent, prefix=".oscar-", suffix=".env.local", delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            stream.writelines(
                f"OPENAI_API_KEY={key}\n" if line.startswith("OPENAI_API_KEY=") else line
                for line in lines
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, env_file)
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
    print("Configured OPENAI_API_KEY. OSCAR_API_KEY was preserved. Restart the normal pilot.")


def validate_application_key(value: str) -> None:
    if value.startswith(("sk-proj-", "sk-svcacct-")):
        raise ValueError(
            "An OpenAI key was placed in OSCAR_API_KEY. Use configure-ai for OPENAI_API_KEY "
            "and keep a separate random application key in OSCAR_API_KEY."
        )


def backup(compose: list[str], directory: Path, database: str) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (directory / "database.dump").open("wb") as output:
        subprocess.run(
            [*compose, "exec", "-T", "db", "pg_dump", "-U", "oscar", "-Fc", database],
            stdout=output,
            check=True,
        )
    with (directory / "pdfs.tar.gz").open("wb") as output:
        subprocess.run(
            [
                *compose,
                "exec",
                "-T",
                "api",
                "python",
                "scripts/archive_pilot_storage.py",
            ],
            stdout=output,
            check=True,
        )
    manifest = {
        "version": 1,
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "files": {name: digest(directory / name) for name in ("database.dump", "pdfs.tar.gz")},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Backup complete: {directory}")


def verify_backup(compose: list[str], directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("version") != 1:
        raise ValueError("Unsupported backup format")
    for name in ("database.dump", "pdfs.tar.gz"):
        source = directory / name
        if source.is_symlink() or manifest["files"].get(name) != digest(source):
            raise ValueError(f"Backup checksum failed for {name}")

    database = f"oscar_restore_check_{secrets.token_hex(8)}"
    subprocess.run([*compose, "exec", "-T", "db", "createdb", "-U", "oscar", database], check=True)
    try:
        with (directory / "database.dump").open("rb") as source:
            subprocess.run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "db",
                    "pg_restore",
                    "-U",
                    "oscar",
                    "-d",
                    database,
                    "--single-transaction",
                    "--exit-on-error",
                ],
                stdin=source,
                check=True,
            )
        count = subprocess.check_output(
            [
                *compose,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "oscar",
                "-d",
                database,
                "-At",
                "-c",
                "SELECT count(*) FROM jobs",
            ],
            text=True,
        ).strip()
        with tempfile.TemporaryDirectory(prefix="oscar-pdf-restore-") as temporary:
            with tarfile.open(directory / "pdfs.tar.gz", "r:gz") as archive:
                archive.extractall(temporary, filter="data")
            pdfs = list(Path(temporary).rglob("*.pdf"))
            for pdf in pdfs:
                with pdf.open("rb") as stream:
                    if stream.read(4) != b"%PDF":
                        raise ValueError("A restored PDF is invalid")
            print(f"Restore check passed: {count} jobs, {len(pdfs)} PDFs.")
    finally:
        # Only the fresh, randomly named restore-check database is removed.
        subprocess.run(
            [*compose, "exec", "-T", "db", "dropdb", "-U", "oscar", database],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["init", "configure-ai", "start", "stop", "status", "backup", "verify-backup"],
    )
    parser.add_argument("--simulation", action="store_true")
    parser.add_argument("--directory", type=Path, help="Backup output or existing backup directory")
    args = parser.parse_args()
    env_file = ROOT / (".env.simulation" if args.simulation else ".env.pilot")
    if env_file.is_symlink():
        parser.error("The configuration file must be a regular file.")
    if args.command == "init":
        initialize(env_file, args.simulation)
        return
    if args.command == "configure-ai":
        if args.simulation:
            parser.error("Simulation does not use an AI key. Configure the normal pilot instead.")
        try:
            configure_ai(env_file)
        except ValueError as error:
            parser.error(str(error))
        return
    if not env_file.is_file():
        parser.error("Run init with the same mode before using this command.")
    values = dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    )
    project = "oscar-simulation" if args.simulation else "oscar-pilot"
    expected_mode = "simulation" if args.simulation else "local"
    if values.get("OSCAR_ENV") != expected_mode:
        parser.error("The selected mode does not match the configuration file.")
    if args.command == "start":
        try:
            validate_application_key(values.get("OSCAR_API_KEY", ""))
        except ValueError as error:
            parser.error(str(error))
    compose = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(env_file),
        "-f",
        str(ROOT / "compose.pilot.yml"),
    ]
    if args.command == "start":
        subprocess.run(
            [*compose, "up", "-d", "--build", "--wait", "--wait-timeout", "180"],
            check=True,
        )
        print("OSCAR is ready at http://127.0.0.1:5173")
    elif args.command == "stop":
        subprocess.run([*compose, "down"], check=True)
        print("Stopped. Database and documents remain in the project volumes.")
    elif args.command == "status":
        subprocess.run([*compose, "ps"], check=True)
    elif args.command == "backup":
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        directory = args.directory or ROOT / "backups" / f"{project}-{stamp}-{secrets.token_hex(3)}"
        backup(compose, directory.resolve(), values["OSCAR_DATABASE_NAME"])
    elif args.command == "verify-backup":
        if not args.directory:
            parser.error("Provide --directory with a backup created by this tool.")
        verify_backup(compose, args.directory.resolve())


if __name__ == "__main__":
    main()
