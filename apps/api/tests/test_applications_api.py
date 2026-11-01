"""Integration tests for application tracking (FR-008/FR-009)."""

from __future__ import annotations

import datetime as dt

import httpx


async def _capture_job(client: httpx.AsyncClient, *, suffix: str = "1") -> int:
    capture = await client.post(
        "/api/v1/jobs/capture",
        json={
            "url": f"https://example.com/jobs/{suffix}",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
            "capture_method": "extension",
            "page_title": "ML Engineer",
            "raw_text": "We need an ML Engineer. " * 10,
        },
    )
    return capture.json()["job_id"]


async def test_create_application_marks_job_applied(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)

    response = await client.post("/api/v1/applications", json={"job_id": job_id})

    assert response.status_code == 201
    assert response.json()["current_status"] == "APPLIED"

    job = await client.get(f"/api/v1/jobs/{job_id}")
    assert job.json()["current_status"] == "APPLIED"
    event_types = [e["event_type"] for e in job.json()["events"]]
    assert "JOB_SAVED" in event_types


async def test_full_happy_path_to_offer(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)
    application = await client.post("/api/v1/applications", json={"job_id": job_id})
    app_id = application.json()["id"]

    assessment = await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "ASSESSMENT_RECEIVED"}
    )
    assert assessment.json()["current_status"] == "ASSESSMENT"

    interview = await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "INTERVIEW_RECEIVED"}
    )
    assert interview.json()["current_status"] == "INTERVIEW"

    final = await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "FINAL_INTERVIEW"}
    )
    assert final.json()["current_status"] == "FINAL_INTERVIEW"

    offer = await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "OFFER_RECEIVED"}
    )
    assert offer.json()["current_status"] == "OFFER"

    detail = await client.get(f"/api/v1/applications/{app_id}")
    event_types = [e["event_type"] for e in detail.json()["events"]]
    assert event_types == [
        "APPLICATION_SUBMITTED",
        "ASSESSMENT_RECEIVED",
        "INTERVIEW_RECEIVED",
        "FINAL_INTERVIEW",
        "OFFER_RECEIVED",
    ]


async def test_multi_round_interview_does_not_look_like_a_reapplication(
    client: httpx.AsyncClient,
) -> None:
    job_id = await _capture_job(client)
    application = await client.post("/api/v1/applications", json={"job_id": job_id})
    app_id = application.json()["id"]

    await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "INTERVIEW_RECEIVED"}
    )
    second_round = await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "INTERVIEW_RECEIVED"}
    )

    assert second_round.status_code == 200
    assert second_round.json()["current_status"] == "INTERVIEW"


async def test_illegal_transition_is_rejected_with_409(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)
    application = await client.post("/api/v1/applications", json={"job_id": job_id})
    app_id = application.json()["id"]

    await client.post(f"/api/v1/applications/{app_id}/events", json={"event_type": "REJECTED"})
    illegal = await client.post(
        f"/api/v1/applications/{app_id}/events", json={"event_type": "OFFER_RECEIVED"}
    )

    assert illegal.status_code == 409
    assert illegal.json()["error_type"] == "ILLEGAL_TRANSITION"

    # The illegal attempt must not have been recorded as an event.
    detail = await client.get(f"/api/v1/applications/{app_id}")
    event_types = [e["event_type"] for e in detail.json()["events"]]
    assert event_types == ["APPLICATION_SUBMITTED", "REJECTED"]


async def test_application_links_the_submitted_cv_version(
    client: httpx.AsyncClient, fake_llm
) -> None:
    job_id = await _capture_job(client)
    exp = await client.post(
        "/api/v1/career-profile/experiences",
        json={
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2022-01-01",
            "is_current": True,
        },
    )
    achievement = await client.post(
        "/api/v1/career-profile/achievements",
        json={
            "statement": "Built things",
            "experience_id": exp.json()["id"],
            "skill_tags": ["python"],
        },
    )
    fake_llm.queue(
        {
            "summary": {
                "text": "Engineer.",
                "supporting_fact_ids": [f"ach_{achievement.json()['id']}"],
            },
            "experience": [],
            "projects": [],
        }
    )
    cv = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    cv_id = cv.json()["cv_version_id"]

    application = await client.post(
        "/api/v1/applications", json={"job_id": job_id, "submitted_cv_version_id": cv_id}
    )

    assert application.json()["submitted_cv_version_id"] == cv_id
    cv_after = await client.get(f"/api/v1/cv/{cv_id}")
    assert cv_after.json()["is_submitted"] is True


async def test_answers_can_be_recorded(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)
    application = await client.post("/api/v1/applications", json={"job_id": job_id})
    app_id = application.json()["id"]

    answer = await client.post(
        f"/api/v1/applications/{app_id}/answers",
        json={"question_key": "notice_period", "answer_text": "1 month"},
    )

    assert answer.status_code == 201
    assert answer.json()["question_key"] == "notice_period"


async def test_skip_and_unskip_a_job(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)

    skipped = await client.post(f"/api/v1/jobs/{job_id}/skip")
    assert skipped.json()["current_status"] == "SKIPPED"

    unskipped = await client.post(f"/api/v1/jobs/{job_id}/unskip")
    assert unskipped.json()["current_status"] == "SAVED"


async def test_job_scoped_application_lookup(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)

    before = await client.get(f"/api/v1/jobs/{job_id}/application")
    assert before.status_code == 200
    assert before.json() is None

    created = await client.post("/api/v1/applications", json={"job_id": job_id})
    after = await client.get(f"/api/v1/jobs/{job_id}/application")

    assert after.json()["id"] == created.json()["id"]


async def test_cannot_skip_an_already_applied_job(client: httpx.AsyncClient) -> None:
    job_id = await _capture_job(client)
    await client.post("/api/v1/applications", json={"job_id": job_id})

    response = await client.post(f"/api/v1/jobs/{job_id}/skip")

    assert response.status_code == 409
