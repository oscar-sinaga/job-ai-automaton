"""Refuse an unsafe simulation database before attempting any connection."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "serve_simulation.py"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://oscar@127.0.0.1/oscar",
        "postgresql+psycopg://oscar@example.com/oscar_simulation_test",
        "postgresql+psycopg://oscar@/oscar_simulation_test",
        "sqlite:///oscar_simulation_test",
        "postgresql+psycopg://oscar@127.0.0.1/oscar_simulation_test?hostaddr=203.0.113.1",
    ],
)
def test_simulation_refuses_nonlocal_or_nonsimulation_database(url: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--database-url", url, "--storage-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "Use a loopback PostgreSQL database named oscar_simulation_*" in result.stderr
    assert not list(tmp_path.iterdir())
