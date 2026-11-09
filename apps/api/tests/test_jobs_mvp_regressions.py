"""JD correction, clock skew, request validation and concurrent capture regressions."""

from __future__ import annotations

import base64
import datetime as dt
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from oscar_api.db import engine
from oscar_api.modules.jobs import service
from oscar_api.modules.jobs.models import Company, Job, JobRawSnapshot, Source
from oscar_api.modules.jobs.schemas import CaptureEnvelope
from test_cv_api import _good_draft, _setup_job_and_profile

JD = "Build reliable Python data pipelines and document reproducible quality checks. " * 5
CORRECTED_JD = "Maintain Python services, review data contracts and improve deployment tests. " * 5


def _capture(**overrides: object) -> dict:
    result: dict[str, object] = {
        "url": "https://example.test/jobs/audit",
        "raw_text": JD,
        "capture_method": "paste_text",
        "captured_at": dt.datetime.now(dt.UTC).isoformat(),
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize("offset", [dt.timedelta(days=1), dt.timedelta(days=-1), dt.timedelta()])
async def test_jd_correction_uses_ingestion_order_and_generates_from_new_text(
    client: httpx.AsyncClient, fake_llm, offset: dt.timedelta
) -> None:
    _, fact_id, experience_id = await _setup_job_and_profile(client)
    captured_at = dt.datetime.now(dt.UTC)
    initial = await client.post(
        "/api/v1/jobs/capture",
        json=_capture(raw_text=None, captured_at=(captured_at + offset).isoformat()),
    )
    job_id = initial.json()["job_id"]
    corrected = await client.post(
        f"/api/v1/jobs/{job_id}/snapshots",
        json={
            "raw_text": JD,
            "capture_method": "paste_text",
            "captured_at": captured_at.isoformat(),
        },
    )
    assert corrected.status_code == 201
    assert corrected.json()["capture_completeness"] == "CAPTURED_COMPLETE"
    assert (await client.get(f"/api/v1/jobs/{job_id}/raw")).json()["raw_text"] == JD
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert detail["snapshots"][0]["raw_text_length"] == 0
    assert detail["snapshots"][1]["id"] == corrected.json()["snapshot_id"]
    fake_llm.queue(_good_draft(f"ach_{fact_id}", experience_id))
    generated = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    assert generated.status_code == 201
    assert fake_llm.calls[-1]["user"] == f"Job description:\n\n{JD}"


@pytest.mark.parametrize("raw", [None, "", " \n\t", "Too short."])
async def test_invalid_correction_keeps_complete_jd_and_history(
    client: httpx.AsyncClient, raw: str | None
) -> None:
    captured = await client.post("/api/v1/jobs/capture", json=_capture())
    job_id = captured.json()["job_id"]
    response = await client.post(
        f"/api/v1/jobs/{job_id}/snapshots",
        json=_capture(raw_text=raw),
    )
    assert response.status_code == 422
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert detail["capture_completeness"] == "CAPTURED_COMPLETE"
    assert len(detail["snapshots"]) == 1
    assert len(detail["events"]) == 1
    assert (await client.get(f"/api/v1/jobs/{job_id}/raw")).json()["raw_text"] == JD


async def test_correcting_complete_jd_retains_original_and_adds_event(client, db_session) -> None:
    captured = await client.post("/api/v1/jobs/capture", json=_capture())
    job_id = captured.json()["job_id"]
    original_id = captured.json()["snapshot_id"]
    response = await client.post(
        f"/api/v1/jobs/{job_id}/snapshots",
        json=_capture(raw_text=CORRECTED_JD),
    )
    assert response.status_code == 201
    assert (await client.get(f"/api/v1/jobs/{job_id}/raw")).json()["raw_text"] == CORRECTED_JD
    original = db_session.get(JobRawSnapshot, original_id)
    assert original is not None and original.raw_text == JD
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert len(detail["snapshots"]) == 2
    assert [event["event_type"] for event in detail["events"]] == ["JOB_SAVED", "JOB_UPDATED"]


@pytest.mark.parametrize(
    "cursor",
    [
        "not-a-cursor",
        "",
        "%%%",
        "a" * 65,
        *[
            base64.urlsafe_b64encode(value.encode()).decode()
            for value in ["0", "-1", "no", "9223372036854775808"]
        ],
    ],
)
async def test_invalid_cursor_is_validation_error(client, cursor: str) -> None:
    response = await client.get("/api/v1/jobs", params={"cursor": cursor})
    assert response.status_code == 422


@pytest.mark.parametrize("age", ["banana", "", "-1d", "5dd", "36501d", "999999999999"])
async def test_invalid_age_is_validation_error(client, age: str) -> None:
    assert (await client.get("/api/v1/jobs", params={"older_than": age})).status_code == 422


@pytest.mark.parametrize("limit", [-1, 0, 201])
async def test_invalid_page_size_is_validation_error(client, limit: int) -> None:
    assert (await client.get("/api/v1/jobs", params={"limit": limit})).status_code == 422


@pytest.mark.parametrize("key", ["", "x" * 65])
async def test_invalid_idempotency_key_does_not_create_job(client, key: str) -> None:
    response = await client.post(
        "/api/v1/jobs/capture", json=_capture(), headers={"Idempotency-Key": key}
    )
    assert response.status_code == 422
    assert (await client.get("/api/v1/jobs")).json()["items"] == []


@pytest.mark.parametrize("field,size", [("source_hint", 101), ("company_name", 301)])
async def test_oversize_capture_metadata_is_validation_error(client, field: str, size: int) -> None:
    response = await client.post("/api/v1/jobs/capture", json=_capture(**{field: "x" * size}))
    assert response.status_code == 422


async def test_backlog_links_include_url_only_jobs_and_exclude_duplicates(client, db_session):
    for _ in range(2):
        await client.post(
            "/api/v1/jobs/capture",
            json=_capture(raw_text=None, capture_method="extension"),
        )
    await client.post(
        "/api/v1/jobs/capture",
        json=_capture(
            url="https://example.test/url-only", raw_text=None, capture_method="manual_url"
        ),
    )
    old_jobs = []
    for _ in range(2):
        response = await client.post(
            "/api/v1/jobs/capture", json=_capture(url="https://example.test/old-ingestion")
        )
        old_jobs.append(response.json()["job_id"])
    for job_id in old_jobs:
        db_session.get(Job, job_id).created_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=8)
    db_session.commit()
    # A device's old clock must not make a newly ingested job appear eight days old.
    await client.post(
        "/api/v1/jobs/capture",
        json=_capture(
            url="https://example.test/old-device-clock",
            captured_at=(dt.datetime.now(dt.UTC) - dt.timedelta(days=8)).isoformat(),
        ),
    )
    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["backlog"]["partial_captures"] == 2
    assert dashboard["backlog"]["saved_older_than_5d"] == 1
    for item in dashboard["action_queue"]:
        linked = await client.get("/api/v1" + item["href"])
        assert linked.status_code == 200
        assert len(linked.json()["items"]) == item["count"], item["label"]
    all_jobs = (await client.get("/api/v1/jobs")).json()["items"]
    assert len(all_jobs) == 6, "General inbox must retain duplicate history"


async def test_skipped_approved_job_leaves_queue_and_unskip_restores_readiness(client, fake_llm):
    job_id, fact_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{fact_id}", experience_id))
    generated = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    assert generated.status_code == 201
    cv_id = generated.json()["cv_version_id"]
    assert (await client.post(f"/api/v1/cv/{cv_id}/approve")).status_code == 200
    assert (await client.get("/api/v1/dashboard")).json()["backlog"]["cv_ready_not_applied"] == 1
    assert (await client.post(f"/api/v1/jobs/{job_id}/skip")).status_code == 200
    skipped = (await client.get("/api/v1/dashboard")).json()
    assert skipped["backlog"]["cv_ready_not_applied"] == 0
    assert skipped["kpis"]["ready_to_apply"] == 0
    assert (await client.get("/api/v1/analytics/productivity")).json()["backlog_size"] == 0
    restored = await client.post(f"/api/v1/jobs/{job_id}/unskip")
    assert restored.json()["current_status"] == "READY_TO_APPLY"
    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["backlog"]["cv_ready_not_applied"] == 1
    assert dashboard["kpis"]["ready_to_apply"] == 1
    assert (await client.get("/api/v1/analytics/productivity")).json()["backlog_size"] == 1
    for item in dashboard["action_queue"]:
        linked = await client.get("/api/v1" + item["href"])
        assert len(linked.json()["items"]) == item["count"], item["label"]


@pytest.mark.parametrize("same_key", [True, False])
def test_overlapping_capture_retries_preserve_idempotency_and_shared_metadata(
    monkeypatch, same_key: bool
) -> None:
    """Committed independent sessions, not the ordinary savepoint client fixture."""
    token = uuid.uuid4().hex
    source_name, company_name = f"audit-{token}.test", f"Synthetic Capture {token}"
    envelope = CaptureEnvelope.model_validate(
        _capture(url=f"https://{source_name}/job/1", company_name=company_name)
    )
    first_source_entered, release_first, second_source_entered = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    counter_lock = threading.Lock()
    calls = 0
    original = service.resolve_source

    def paused_source(session, source_hint, url):
        nonlocal calls
        with counter_lock:
            calls += 1
            number = calls
        if number == 1:
            first_source_entered.set()
            assert release_first.wait(10), "capture coordination timed out"
        else:
            second_source_entered.set()
        return original(session, source_hint, url)

    monkeypatch.setattr(service, "resolve_source", paused_source)

    def capture(key):
        with Session(engine) as session:
            job, _, created = service.capture_job(session, envelope, key)
            return job.id, created, job.duplicate_of_job_id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(capture, token)
            assert first_source_entered.wait(10)
            second = pool.submit(capture, token if same_key else uuid.uuid4().hex)
            # Without serialization the second request reaches source creation
            # before the first request commits its idempotency key.
            second_source_entered.wait(0.5)
            release_first.set()
            one, two = first.result(timeout=15), second.result(timeout=15)
        if same_key:
            assert one[0] == two[0]
            assert (one[1], two[1]) == (True, False)
        else:
            assert one[0] != two[0] and one[1] and two[1]
            assert two[2] == one[0]
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count()).select_from(Source).where(Source.name == source_name)
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count()).select_from(Company).where(Company.name == company_name)
                )
                == 1
            )
    finally:
        release_first.set()
        with Session(engine) as session:
            session.execute(delete(Job).where(Job.url == envelope.url))
            session.execute(delete(Source).where(Source.name == source_name))
            session.execute(delete(Company).where(Company.name == company_name))
            session.commit()
