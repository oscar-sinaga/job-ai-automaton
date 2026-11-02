"""The documented first-run configuration must load before the API can start."""

import pytest

from oscar_api.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://127.0.0.1:5173", ["http://127.0.0.1:5173"]),
        (
            "http://127.0.0.1:5173, http://localhost:5173",
            ["http://127.0.0.1:5173", "http://localhost:5173"],
        ),
        ('["http://127.0.0.1:5173"]', ["http://127.0.0.1:5173"]),
    ],
)
def test_documented_cors_environment_values_load(monkeypatch, raw, expected):
    monkeypatch.setenv("OSCAR_CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == expected


def test_default_cors_origins_remain_local(monkeypatch):
    monkeypatch.delenv("OSCAR_CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == ["http://127.0.0.1:5173"]
