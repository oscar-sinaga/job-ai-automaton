"""Exercise only isolated helper processes and synthetic state under pytest's tmp dir."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="WSL helper requires Linux /proc")


@pytest.fixture
def helper(tmp_path):
    script = tmp_path / "scripts/windows/hold-wsl.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/windows/hold-wsl.py", script)
    state = tmp_path / "var/logs/fixture.linux.json"
    state.parent.mkdir(parents=True)
    return script, state


def arguments(script, state, token, *extra):
    return [sys.executable, str(script), "--state-file", str(state), "--token", token, *extra]


def wait_for_state(process, state, token):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail("Fixture helper exited before publishing its state")
        try:
            record = json.loads(state.read_text())
        except (FileNotFoundError, ValueError):
            pass
        else:
            if record["token"] == token:
                return record
        time.sleep(0.02)
    pytest.fail("Fixture helper did not publish state")


def stop_fixture(process, script, state, token):
    try:
        result = subprocess.run(arguments(script, state, token, "--stop"), timeout=5)
        assert result.returncode == 0
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.terminate()  # Only the subprocess created by this test.
            process.wait(timeout=5)


def test_restart_recovers_reused_pid_without_signalling_unrelated_process(helper):
    script, state = helper
    state.write_text(
        json.dumps(
            {"pid": os.getpid(), "token": "0" * 32, "script": str(script), "start_ticks": "stale"}
        )
    )
    token = "1" * 32
    process = subprocess.Popen(arguments(script, state, token))
    try:
        record = wait_for_state(process, state, token)
        assert record["pid"] == process.pid
        os.kill(os.getpid(), 0)
    finally:
        stop_fixture(process, script, state, token)
    assert not state.exists()


def test_live_matching_helper_keeps_ownership_and_rejects_second_helper(helper):
    script, state = helper
    token = "2" * 32
    process = subprocess.Popen(arguments(script, state, token))
    try:
        first = wait_for_state(process, state, token)
        second = subprocess.run(arguments(script, state, "3" * 32), timeout=5)
        assert second.returncode == 2
        assert json.loads(state.read_text()) == first
        assert process.poll() is None
        wrong_stop = subprocess.run(arguments(script, state, "4" * 32, "--stop"), timeout=5)
        assert wrong_stop.returncode == 2
        assert process.poll() is None
    finally:
        stop_fixture(process, script, state, token)


def test_stop_clears_owned_stale_record_without_signalling_reused_pid(helper):
    script, state = helper
    token = "5" * 32
    state.write_text(
        json.dumps(
            {"pid": os.getpid(), "token": token, "script": str(script), "start_ticks": "stale"}
        )
    )
    result = subprocess.run(arguments(script, state, token, "--stop"), timeout=5)
    assert result.returncode == 0
    assert not state.exists()
    os.kill(os.getpid(), 0)


def test_unrecognized_record_and_escaping_state_path_are_left_untouched(helper, tmp_path):
    script, state = helper
    original = json.dumps({"pid": os.getpid(), "token": "6" * 32, "script": "/other/helper"})
    state.write_text(original)
    assert subprocess.run(arguments(script, state, "7" * 32), timeout=5).returncode == 2
    assert state.read_text() == original
    outside = tmp_path.parent / "outside-fixture.linux.json"
    assert subprocess.run(arguments(script, outside, "8" * 32), timeout=5).returncode == 2
    assert not outside.exists()
