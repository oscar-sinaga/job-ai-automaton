"""Keep an explicitly launched WSL client alive until its owned helper is stopped."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import tempfile
import threading
from contextlib import contextmanager, suppress
from pathlib import Path


def process_state(state: dict[str, object], script: Path, token: str) -> str:
    """Only a readable identity mismatch or absent process proves a stale PID."""
    try:
        pid = int(state["pid"])
        if pid <= 1 or state["token"] != token or state["script"] != str(script):
            return "unknown"
        process = Path("/proc") / str(pid)
        arguments = (process / "cmdline").read_bytes().split(b"\0")
        start_ticks = (process / "stat").read_text().rsplit(")", 1)[1].split()[19]
        matches = (
            len(arguments) > 2
            and arguments[1] == os.fsencode(script)
            and b"--token" in arguments
            and arguments[arguments.index(b"--token") + 1] == token.encode("ascii")
            and start_ticks == state["start_ticks"]
        )
        return "owned" if matches else "stale"
    except (FileNotFoundError, ProcessLookupError):
        return "stale"
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return "unknown"


def process_matches(state: dict[str, object], script: Path, token: str) -> bool:
    return process_state(state, script, token) == "owned"


def read_state(path: Path) -> dict[str, object]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, encoding="utf-8") as stream:
        state = json.load(stream)
    if not isinstance(state, dict):
        raise ValueError("Invalid helper state")
    return state


@contextmanager
def state_lock(path: Path):
    descriptor = os.open(
        path.with_name(path.name + ".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def write_state(path: Path, state: dict[str, object]) -> None:
    """Readers see either the old complete record or the new complete record."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".pilot-helper-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--token", required=True)
    parser.add_argument("--stop", action="store_true")
    options = parser.parse_args()
    if len(options.token) != 32 or any(c not in "0123456789abcdef" for c in options.token):
        parser.error("The ownership token must be a lowercase UUID hex value.")

    script = Path(__file__).resolve()
    repository = script.parents[2]
    logs = repository / "var" / "logs"
    state_file = options.state_file.resolve()
    if (
        not logs.resolve().is_relative_to(repository)
        or options.state_file.is_symlink()
        or state_file.parent != logs.resolve()
        or not state_file.name.endswith(".linux.json")
    ):
        parser.error("The state file must be an owned .linux.json file under var/logs.")

    if options.stop:
        if not logs.is_dir():
            return 0
        with state_lock(state_file):
            if not state_file.exists():
                return 0
            try:
                state = read_state(state_file)
                pid = int(state.get("pid", 0))
            except (OSError, ValueError, TypeError):
                return 2
            if state.get("token") != options.token or state.get("script") != str(script):
                return 2
            ownership = process_state(state, script, options.token)
            if ownership == "unknown":
                return 2
            if ownership == "stale":
                # A reused PID is unrelated: clear only this stale record, never signal it.
                state_file.unlink(missing_ok=True)
                return 0
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGTERM)
        return 0

    logs.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    for event in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(event, lambda *_: stop.set())
    pid = os.getpid()
    state = {
        "pid": pid,
        "token": options.token,
        "script": str(script),
        "start_ticks": Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19],
    }
    with state_lock(state_file):
        if state_file.exists():
            try:
                previous = read_state(state_file)
            except (OSError, ValueError):
                return 2  # An unreadable record cannot safely be classified as stale.
            previous_token = previous.get("token")
            if not isinstance(previous_token, str) or previous.get("script") != str(script):
                return 2
            if process_state(previous, script, previous_token) != "stale":
                return 2  # The existing matching helper remains in charge.
        write_state(state_file, state)
    try:
        stop.wait()
    finally:
        try:
            with state_lock(state_file):
                current = read_state(state_file)
                if current.get("pid") == pid and current.get("token") == options.token:
                    state_file.unlink()
        except (OSError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
