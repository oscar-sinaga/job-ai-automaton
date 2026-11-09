"""Provider credentials must not become the web/extension application's key."""

import importlib.util
import io
import sys
import tarfile
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


def test_configuration_owns_compose_values_without_losing_system_environment(monkeypatch):
    monkeypatch.setenv("OSCAR_ENV", "simulation")
    monkeypatch.setenv("OSCAR_API_KEY", "sk-proj-inherited-synthetic-key")
    monkeypatch.setenv("OSCAR_API_PORT", "9999")
    monkeypatch.setenv("POSTGRES_PASSWORD", "inherited-synthetic-password")
    monkeypatch.setenv("OPENAI_API_KEY", "inherited-synthetic-provider-key")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.fixture:8080")
    monkeypatch.setenv("DOCKER_HOST", "unix:///fixture/docker.sock")
    environment = pilot.compose_environment(
        {"OSCAR_ENV": "local", "OSCAR_API_KEY": "fixture-app-key", "PATH": "ignore-this"}
    )
    assert environment["OSCAR_ENV"] == "local"
    assert environment["OSCAR_API_KEY"] == "fixture-app-key"
    assert "OSCAR_API_PORT" not in environment
    assert "POSTGRES_PASSWORD" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert environment["PATH"] != "ignore-this"
    assert environment["HTTP_PROXY"] == "http://proxy.fixture:8080"
    assert environment["DOCKER_HOST"] == "unix:///fixture/docker.sock"


def test_literal_configuration_handles_bom_comments_and_quotes(tmp_path):
    env = tmp_path / "synthetic.cfg"
    env.write_text("\ufeff # comment\nexport OSCAR_ENV = \"local\"\nOPENAI_API_KEY='fixture'\n")
    assert pilot.read_configuration(env) == {"OSCAR_ENV": "local", "OPENAI_API_KEY": "fixture"}


@pytest.mark.parametrize("command", ["start", "stop", "status", "backup", "verify-backup"])
def test_every_cli_command_uses_selected_file_environment(tmp_path, monkeypatch, command):
    env = tmp_path / ".env.pilot"
    env.write_text(
        "OSCAR_ENV=local\nOSCAR_API_KEY=fixture-app-key\n"
        "OSCAR_DATABASE_NAME=oscar_fixture\nPOSTGRES_PASSWORD=fixture-password\n"
    )
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    monkeypatch.setenv("OSCAR_ENV", "simulation")
    monkeypatch.setenv("OSCAR_API_KEY", "sk-proj-inherited-synthetic-key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "inherited-password")
    calls = []

    def record(*args, **kwargs):
        calls.append(kwargs["environment"] if "environment" in kwargs else kwargs["env"])

    monkeypatch.setattr(pilot.subprocess, "run", record)
    monkeypatch.setattr(pilot, "backup", record)
    monkeypatch.setattr(pilot, "verify_backup", record)
    monkeypatch.setattr(sys, "argv", ["pilot.py", command, "--directory", str(tmp_path / "backup")])
    pilot.main()
    assert calls
    assert all(call["OSCAR_ENV"] == "local" for call in calls)
    assert all(call["OSCAR_API_KEY"] == "fixture-app-key" for call in calls)
    assert all(call["POSTGRES_PASSWORD"] == "fixture-password" for call in calls)


def test_backup_and_restore_checks_pass_environment_to_every_subprocess(tmp_path, monkeypatch):
    environment = {"OSCAR_ENV": "local", "PATH": "fixture-path"}
    calls = []
    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w:gz"):
        pass

    def run(arguments, **kwargs):
        calls.append(kwargs["env"])
        if "stdout" in kwargs:
            kwargs["stdout"].write(
                b"synthetic-dump" if "pg_dump" in arguments else archive_bytes.getvalue()
            )

    def check_output(arguments, **kwargs):
        calls.append(kwargs["env"])
        return "0\n"

    monkeypatch.setattr(pilot.subprocess, "run", run)
    monkeypatch.setattr(pilot.subprocess, "check_output", check_output)
    directory = tmp_path / "backup"
    pilot.backup(["fixture-compose"], directory, "oscar_fixture", environment=environment)
    pilot.verify_backup(["fixture-compose"], directory, environment=environment)
    assert len(calls) == 6
    assert all(call is environment for call in calls)
