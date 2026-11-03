"""Provider credentials must not become the web/extension application's key."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("pilot", ROOT / "scripts/pilot.py")
assert spec and spec.loader
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def test_hidden_key_setup_preserves_app_key_without_printing_provider_key(
    tmp_path, monkeypatch, capsys
):
    env = tmp_path / "pilot.env.local"
    pilot.initialize(env, False)
    before = dict(line.split("=", 1) for line in env.read_text().splitlines())
    key = "sk-" + "synthetic-key-for-offline-test-only"
    monkeypatch.setattr(pilot.getpass, "getpass", lambda _: key)
    pilot.configure_ai(env)
    after = dict(line.split("=", 1) for line in env.read_text().splitlines())
    assert after["OPENAI_API_KEY"] == key
    assert after["OSCAR_API_KEY"] == before["OSCAR_API_KEY"]
    assert after["POSTGRES_PASSWORD"] == before["POSTGRES_PASSWORD"]
    assert env.stat().st_mode & 0o777 == 0o600
    assert key not in capsys.readouterr().out


def test_invalid_provider_key_does_not_change_configuration(tmp_path, monkeypatch):
    env = tmp_path / "pilot.env.local"
    pilot.initialize(env, False)
    original = env.read_bytes()
    monkeypatch.setattr(pilot.getpass, "getpass", lambda _: "not-a-provider-key")
    with pytest.raises(ValueError, match="not changed"):
        pilot.configure_ai(env)
    assert env.read_bytes() == original


def test_provider_key_cannot_be_used_as_application_key():
    key = "sk-" + "proj-" + "synthetic-key-for-offline-test-only"
    with pytest.raises(ValueError, match="separate random application key"):
        pilot.validate_application_key(key)
    pilot.validate_application_key("a-separate-random-application-key")
