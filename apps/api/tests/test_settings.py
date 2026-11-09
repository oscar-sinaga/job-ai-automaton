"""Settings acceptance against real isolated PostgreSQL and synthetic artifacts."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import zipfile
from contextlib import aclosing

import pytest
from sqlalchemy import func, select

from oscar_api.adapters.local_storage import LocalFileStorage
from oscar_api.config import get_settings
from oscar_api.core.models import SINGLE_USER_ID, User
from oscar_api.modules.career.models import CareerAchievement, CareerExperience, CareerProfile
from oscar_api.modules.cv.models import CVArtifact, CVGenerationRun, CVVersion
from oscar_api.modules.jobs.models import CaptureCompleteness, CaptureMethod, Job, JobRawSnapshot
from oscar_api.modules.settings.models import PendingFileDeletion, UserSettings


def seed_job(session, storage=None):
    job = Job(
        user_id=SINGLE_USER_ID,
        ref="JSETTINGS",
        url="https://example.test/career/settings",
        capture_completeness=CaptureCompleteness.CAPTURED_COMPLETE,
    )
    session.add(job)
    session.flush()
    job.ref = f"J{job.id:03d}"
    session.add(
        JobRawSnapshot(
            job_id=job.id,
            capture_method=CaptureMethod.paste_text,
            raw_text="Reporting systems and data quality engineering. " * 12,
            page_title="Synthetic engineer",
            captured_at=dt.datetime.now(dt.UTC),
        )
    )
    if storage is not None:
        version = CVVersion(
            job_id=job.id,
            version_number=1,
            sections={
                "summary": {"text": "Synthetic fact", "supporting_fact_ids": []},
                "experience": [],
                "projects": [],
                "skills": [],
                "missing_requirements": [],
            },
        )
        session.add(version)
        session.flush()
        uri = storage.save(
            relative_path=f"cv/{version.label}.pdf", data=b"%PDF-1.4 synthetic-export"
        )
        session.add(CVArtifact(cv_version_id=version.id, storage_uri=uri))
    session.commit()
    return job


async def preview(client, scope="jobs"):
    r = await client.post("/api/v1/settings/data/preview", json={"scope": scope})
    assert r.status_code == 200, r.text
    return r.json()


def deletion_body(p):
    return {"scope": p["scope"], "token": p["token"], "confirmation": p["confirmation_phrase"]}


async def test_preferences_persist_and_reject_credentials(client):
    initial = (await client.get("/api/v1/settings")).json()
    assert initial["default_cv_preferences"] == {
        "language": "en",
        "layout": "standard",
        "max_bullets_per_role": 5,
    }
    prefs = {"language": "id", "layout": "compact", "max_bullets_per_role": 2}
    r = await client.put("/api/v1/settings", json={"default_cv_preferences": prefs})
    assert r.status_code == 200 and r.json()["updated_at"]
    assert (await client.get("/api/v1/settings")).json()["default_cv_preferences"] == prefs
    assert (
        await client.put("/api/v1/settings/integrations", json={"api_key": "must-not-be-stored"})
    ).status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("language", "invalid"),
        ("layout", "unsafe"),
        ("max_bullets_per_role", 0),
        ("max_bullets_per_role", 9),
        ("max_bullets_per_role", True),
    ],
)
async def test_preference_boundaries(client, field, value):
    prefs = {"language": "en", "layout": "standard", "max_bullets_per_role": 5, field: value}
    assert (
        await client.put("/api/v1/settings", json={"default_cv_preferences": prefs})
    ).status_code == 422


async def test_integration_preferences_reach_the_provider_factory(client, db_session, monkeypatch):
    from oscar_api.modules.cv import deps

    captured = {}

    class Adapter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def aclose(self):
            captured["closed"] = True

    monkeypatch.setattr(get_settings(), "openai_api_key", "synthetic-provider-credential")
    monkeypatch.setattr(deps, "OpenAILLMProvider", Adapter)
    r = await client.put(
        "/api/v1/settings/integrations", json={"model": "gpt-6-luna", "max_output_tokens": 2048}
    )
    assert r.status_code == 200
    async with aclosing(deps.get_llm_provider(db_session)) as generator:
        await anext(generator)
    assert captured == {"model": "gpt-6-luna", "max_output_tokens": 2048, "closed": True}
    status = await client.get("/api/v1/settings/integrations")
    assert status.json()["max_output_tokens"] == 2048
    assert status.json()["provider_key_configured"] is True
    assert "synthetic-provider-credential" not in status.text
    assert "test-local-key" not in status.text


@pytest.mark.parametrize(
    "body",
    [
        {"model": "https://untrusted.example"},
        {"max_output_tokens": 0},
        {"max_output_tokens": 16001},
        {"max_output_tokens": True},
        {"OPENAI_API_KEY": "no"},
    ],
)
async def test_integration_boundaries(client, body):
    assert (await client.put("/api/v1/settings/integrations", json=body)).status_code == 422


async def test_every_settings_surface_requires_api_auth(client):
    for method, path, body in [
        ("GET", "/settings", None),
        ("GET", "/settings/integrations", None),
        ("GET", "/export", None),
        ("PUT", "/settings", {"default_cv_preferences": {}}),
        ("POST", "/settings/data/preview", {"scope": "jobs"}),
        (
            "POST",
            "/settings/data/delete",
            {"scope": "jobs", "token": "x" * 43, "confirmation": "DELETE MY JOBS"},
        ),
        ("POST", "/settings/files/retry", {}),
    ]:
        r = await client.request(
            method, "/api/v1" + path, json=body, headers={"X-API-Key": "wrong-key"}
        )
        assert r.status_code == 401, (path, r.text)


async def test_zip_export_is_complete_checksummed_and_private(
    client, db_session, fake_storage, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "storage_dir", tmp_path)
    seed_job(db_session, fake_storage)
    p = await preview(client)
    r = await client.get("/api/v1/export?format=zip")
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        data = archive.read("data.json")
        manifest = json.loads(archive.read("manifest.json"))
        exported = json.loads(data)["tables"]
        assert len(exported["jobs"]) == 1 and len(exported["cv_artifacts"]) == 1
        assert manifest["data_sha256"] == hashlib.sha256(data).hexdigest()
        assert len(manifest["files"]) == 1
        info = manifest["files"][0]
        assert hashlib.sha256(archive.read(info["file"])).hexdigest() == info["sha256"]
        assert "deletion_token_hash" not in data.decode()
        assert p["token"] not in data.decode() and "test-local-key" not in data.decode()
        assert "pending_file_deletions" not in exported
    assert not list((tmp_path / ".exports").glob("export-*")), (
        "Completed download must clean its temporary file"
    )


async def test_export_missing_pdf_never_returns_partial_archive(
    client, db_session, fake_storage, tmp_path, monkeypatch
):
    monkeypatch.setattr(get_settings(), "storage_dir", tmp_path)
    seed_job(db_session, fake_storage)
    fake_storage.saved.clear()
    r = await client.get("/api/v1/export?format=zip")
    assert r.status_code == 503
    assert not list((tmp_path / ".exports").glob("export-*"))
    # Structured data remains exportable for recovery, even without a PDF.
    assert (await client.get("/api/v1/export?format=json")).status_code == 200


async def test_job_deletion_keeps_profile_and_prevents_replay(client, db_session, fake_storage):
    seed_job(db_session, fake_storage)
    profile = db_session.scalar(select(CareerProfile))
    profile.summary = "Synthetic preserved profile"
    db_session.commit()
    p = await preview(client)
    assert p["counts"]["jobs"] == 1
    r = await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    assert r.status_code == 200, r.text
    assert r.json()["files_deleted"] == 1 and r.json()["pending_file_deletions"] == 0
    assert not fake_storage.saved
    assert db_session.scalar(select(func.count()).select_from(Job)) == 0
    assert (await client.get("/api/v1/career-profile")).json()[
        "summary"
    ] == "Synthetic preserved profile"
    assert (
        await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    ).status_code == 409


async def test_all_data_reset_leaves_a_usable_account_and_empty_profile(
    client, db_session, fake_storage
):
    seed_job(db_session, fake_storage)
    profile = db_session.scalar(select(CareerProfile))
    profile.summary = "Synthetic private profile"
    db_session.commit()
    await client.put("/api/v1/settings", json={"default_cv_preferences": {"language": "id"}})
    p = await preview(client, "all")
    r = await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    assert r.status_code == 200, r.text
    assert db_session.get(User, SINGLE_USER_ID) is not None
    profile = await client.get("/api/v1/career-profile")
    assert profile.status_code == 200 and profile.json()["summary"] is None
    assert (await client.get("/api/v1/settings")).json()["default_cv_preferences"][
        "language"
    ] == "en"
    assert db_session.scalar(select(func.count()).select_from(Job)) == 0
    assert not fake_storage.saved


async def test_confirmation_expiry_and_changed_counts_fail_closed(client, db_session):
    seed_job(db_session)
    p = await preview(client)
    wrong = deletion_body(p) | {"confirmation": "yes"}
    assert (await client.post("/api/v1/settings/data/delete", json=wrong)).status_code == 422
    row = db_session.get(UserSettings, SINGLE_USER_ID)
    row.deletion_expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    db_session.commit()
    assert (
        await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    ).status_code == 409
    p = await preview(client)
    seed_job(db_session)
    assert (
        await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    ).status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Job)) == 2


async def test_failed_file_cleanup_is_durable_and_retried(
    client, db_session, fake_storage, monkeypatch
):
    seed_job(db_session, fake_storage)
    original = fake_storage.delete

    def unavailable(uri):
        raise OSError("synthetic filesystem failure")

    monkeypatch.setattr(fake_storage, "delete", unavailable)
    p = await preview(client)
    r = await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    assert r.status_code == 200 and r.json()["pending_file_deletions"] == 1
    assert db_session.scalar(select(func.count()).select_from(Job)) == 0
    assert db_session.scalar(select(func.count()).select_from(PendingFileDeletion)) == 1
    monkeypatch.setattr(fake_storage, "delete", original)
    r = await client.post("/api/v1/settings/files/retry", json={})
    assert r.json() == {"files_deleted": 1, "pending_file_deletions": 0}


async def test_cleanup_database_failure_does_not_report_committed_reset_as_failed(
    client, db_session, fake_storage, monkeypatch
):
    from sqlalchemy.exc import OperationalError

    from oscar_api.modules.settings import deletion

    seed_job(db_session, fake_storage)
    p = await preview(client)

    def unavailable(*args):
        raise OperationalError("synthetic cleanup outage", {}, None)

    monkeypatch.setattr(deletion, "drain_file_deletions", unavailable)
    r = await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    assert r.status_code == 200 and r.json()["pending_file_deletions"] == 1
    assert db_session.scalar(select(func.count()).select_from(Job)) == 0
    assert db_session.scalar(select(func.count()).select_from(PendingFileDeletion)) == 1
    assert (await client.get("/api/v1/settings")).json()["pending_file_deletions"] == 1
    assert (
        await client.post("/api/v1/settings/data/delete", json=deletion_body(p))
    ).status_code == 409


@pytest.mark.parametrize(
    "uri",
    [
        "file://../outside.txt",
        "file:///outside.txt",
        "file://..\\outside.txt",
        "https://example.test/file",
    ],
)
def test_storage_paths_cannot_escape_application_directory(tmp_path, uri):
    root = tmp_path / "artifacts"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic retained file")
    storage = LocalFileStorage(root)
    with pytest.raises(ValueError):
        storage.delete(uri)
    with pytest.raises(ValueError):
        storage.load(uri)
    assert outside.read_text() == "synthetic retained file"


def test_artifact_export_reads_bounded_chunks(tmp_path):
    storage = LocalFileStorage(tmp_path)
    data = b"%PDF synthetic" * 60000
    uri = storage.save(relative_path="cv/large.pdf", data=data)
    chunks = list(storage.iter_load(uri))
    assert len(chunks) > 1 and max(map(len, chunks)) <= 256 * 1024
    assert b"".join(chunks) == data


async def test_saved_cv_preferences_are_sent_applied_and_snapshotted(client, db_session, fake_llm):
    job = seed_job(db_session)
    profile = db_session.scalar(select(CareerProfile))
    exp = CareerExperience(
        profile_id=profile.id,
        company="Example",
        title="Engineer",
        start_date=dt.date(2020, 1, 1),
        is_current=True,
    )
    db_session.add(exp)
    db_session.flush()
    facts = []
    for statement in [
        "Built reliable reporting systems.",
        "Maintained verified data quality checks.",
    ]:
        fact = CareerAchievement(profile_id=profile.id, experience_id=exp.id, statement=statement)
        db_session.add(fact)
        db_session.flush()
        facts.append(fact)
    db_session.commit()
    db_session.expire(profile)
    prefs = {"language": "id", "layout": "compact", "max_bullets_per_role": 1}
    await client.put("/api/v1/settings", json={"default_cv_preferences": prefs})
    fake_llm.queue(
        {
            "summary": {"text": "", "supporting_fact_ids": []},
            "experience": [
                {
                    "experience_id": exp.id,
                    "bullets": [
                        {"text": fact.statement, "supporting_fact_ids": [f"ach_{fact.id}"]}
                        for fact in facts
                    ],
                }
            ],
            "projects": [],
            "skills": [],
            "missing_requirements": [],
        }
    )
    r = await client.post(f"/api/v1/jobs/{job.id}/generate-cv", json={})
    assert r.status_code == 201, r.text
    assert r.json()["sections"]["preferences"] == prefs
    assert len(r.json()["sections"]["experience"][0]["bullets"]) == 1
    run = db_session.scalar(select(CVGenerationRun).where(CVGenerationRun.job_id == job.id))
    assert run.preferences == prefs and run.prompt_version == "cv_generator/v4"
    assert any('"language": "id"' in block.text for block in fake_llm.calls[0]["system"])
