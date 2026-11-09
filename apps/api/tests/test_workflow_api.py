"""Submission truth and complete, append-only job timeline regressions."""

import datetime as dt

from oscar_api.modules.applications.models import Application, ApplicationEvent
from oscar_api.modules.jobs.models import JobEvent
from test_applications_api import _capture_job
from test_cv_regressions import _generate


async def test_recorded_submission_cannot_be_replaced_by_a_different_cv(client, fake_llm):
    job_id, first_id = await _generate(client, fake_llm)
    original = (await client.get(f"/api/v1/cv/{first_id}")).json()
    second = await client.patch(f"/api/v1/cv/{first_id}", json={"sections": original["sections"]})
    second_id = second.json()["id"]
    application = (
        await client.post(
            "/api/v1/applications",
            json={
                "job_id": job_id,
                "submitted_cv_version_id": first_id,
            },
        )
    ).json()
    conflict = await client.post(f"/api/v1/cv/{second_id}/mark-submitted")
    assert conflict.status_code == 409
    assert conflict.json()["error_type"] == "CONFLICT"
    repeated = await client.post(f"/api/v1/cv/{first_id}/mark-submitted")
    assert repeated.status_code == 200
    assert repeated.json()["is_submitted"]
    assert not (await client.get(f"/api/v1/cv/{second_id}")).json()["is_submitted"]
    recorded = (await client.get(f"/api/v1/applications/{application['id']}")).json()
    assert recorded["submitted_cv_version_id"] == first_id
    assert (await client.get(f"/api/v1/cv/{first_id}")).json()["sections"] == original["sections"]


async def test_application_with_unknown_cv_clears_unbacked_manual_marker(client, fake_llm):
    job_id, cv_id = await _generate(client, fake_llm)
    assert (await client.post(f"/api/v1/cv/{cv_id}/mark-submitted")).status_code == 200
    application = await client.post("/api/v1/applications", json={"job_id": job_id})
    assert application.status_code == 201
    assert application.json()["submitted_cv_version_id"] is None
    assert not (await client.get(f"/api/v1/cv/{cv_id}")).json()["is_submitted"]
    # Selecting a CV later must not silently rewrite what this application recorded.
    assert (await client.post(f"/api/v1/cv/{cv_id}/mark-submitted")).status_code == 409


async def test_timeline_includes_all_historical_applications_and_stable_ties(client, db_session):
    job_id = await _capture_job(client, suffix="timeline-history")
    old = Application(job_id=job_id)
    current = Application(job_id=job_id)
    db_session.add_all([old, current])
    db_session.flush()
    timestamp = dt.datetime(2025, 1, 2, 12, tzinfo=dt.UTC)
    db_session.add(
        JobEvent(
            job_id=job_id,
            event_type="CV_APPROVED",
            actor="user",
            event_metadata={"fixture": "job-tie"},
            occurred_at=timestamp,
        )
    )
    db_session.add_all(
        [
            ApplicationEvent(
                application_id=application.id,
                event_type=kind,
                actor="user",
                event_metadata={"fixture": marker},
                occurred_at=timestamp,
            )
            for application, kind, marker in [
                (old, "APPLICATION_SUBMITTED", "old-submitted"),
                (old, "INTERVIEW_RECEIVED", "old-interview-one"),
                (old, "INTERVIEW_RECEIVED", "old-interview-two"),
                (current, "APPLICATION_SUBMITTED", "current-submitted"),
                (current, "INTERVIEW_COMPLETED", "current-interview"),
            ]
        ]
    )
    db_session.commit()
    first = await client.get(f"/api/v1/jobs/{job_id}/timeline")
    second = await client.get(f"/api/v1/jobs/{job_id}/timeline")
    assert first.status_code == 200
    assert first.json() == second.json()
    timeline = first.json()
    assert [item["metadata"]["fixture"] for item in timeline if "fixture" in item["metadata"]] == [
        "job-tie",
        "old-submitted",
        "old-interview-one",
        "old-interview-two",
        "current-submitted",
        "current-interview",
    ]
    assert all(set(item) == {"event_type", "actor", "metadata", "occurred_at"} for item in timeline)
    assert [item["occurred_at"] for item in timeline] == sorted(
        item["occurred_at"] for item in timeline
    )
    assert all(item["actor"] == "user" for item in timeline)


async def test_timeline_requires_authentication_and_a_real_job(client):
    assert (await client.get("/api/v1/jobs/987654321/timeline")).status_code == 404
    denied = await client.get("/api/v1/jobs/987654321/timeline", headers={"X-API-Key": "wrong"})
    assert denied.status_code == 401
