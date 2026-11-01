"""Integration tests for analytics (docs/10_ANALYTICS_DEFINITIONS.md).

Builds a small, hand-counted fixture through the real API -- a skipped job, a
withdrawn application, a job rejected after reaching interview, and a job
that skips straight from APPLIED to INTERVIEW (no assessment) and goes all
the way to OFFER via a 2-round interview -- plus a duplicate, to confirm
duplicates never enter the count (docs/10 D2). Expected numbers are computed
by hand in the comments below, not derived from the code under test.
"""

from __future__ import annotations

import datetime as dt

import httpx


async def _capture(client: httpx.AsyncClient, url: str, title: str) -> int:
    response = await client.post(
        "/api/v1/jobs/capture",
        json={
            "url": url,
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
            "capture_method": "extension",
            "page_title": title,
            "raw_text": "A real job description. " * 10,
        },
    )
    return response.json()["job_id"]


async def _apply(client: httpx.AsyncClient, job_id: int) -> int:
    response = await client.post("/api/v1/applications", json={"job_id": job_id})
    return response.json()["id"]


async def _event(client: httpx.AsyncClient, app_id: int, event_type: str) -> None:
    await client.post(f"/api/v1/applications/{app_id}/events", json={"event_type": event_type})


async def _build_fixture(client: httpx.AsyncClient) -> None:
    # A: saved only, never applied.
    await _capture(client, "https://example.com/jobs/a", "Job A")

    # B: saved, then skipped.
    job_b = await _capture(client, "https://example.com/jobs/b", "Job B")
    await client.post(f"/api/v1/jobs/{job_b}/skip")

    # C: applied, then withdrawn.
    job_c = await _capture(client, "https://example.com/jobs/c", "Job C")
    app_c = await _apply(client, job_c)
    await _event(client, app_c, "WITHDRAWN")

    # D: applied -> assessment -> interview -> rejected.
    job_d = await _capture(client, "https://example.com/jobs/d", "Job D")
    app_d = await _apply(client, job_d)
    await _event(client, app_d, "ASSESSMENT_RECEIVED")
    await _event(client, app_d, "INTERVIEW_RECEIVED")
    await _event(client, app_d, "REJECTED")

    # E: applied -> interview (no assessment) -> 2nd round -> final -> offer.
    job_e = await _capture(client, "https://example.com/jobs/e", "Job E")
    app_e = await _apply(client, job_e)
    await _event(client, app_e, "INTERVIEW_RECEIVED")
    await _event(client, app_e, "INTERVIEW_RECEIVED")  # 2nd round -- must not double count
    await _event(client, app_e, "FINAL_INTERVIEW")
    await _event(client, app_e, "OFFER_RECEIVED")

    # F: duplicate of A (same URL) -- must be excluded from every count.
    await _capture(client, "https://example.com/jobs/a", "Job A (duplicate share)")


async def test_funnel_matches_hand_count(client: httpx.AsyncClient) -> None:
    await _build_fixture(client)

    response = await client.get("/api/v1/analytics/funnel")
    stages = {s["stage"]: s["count"] for s in response.json()}

    # SAVED excludes B (SKIPPED) per docs/10 §4 -- A, C, D, E = 4.
    assert stages["SAVED"] == 4
    # APPLIED: C, D, E = 3 (A never applied, B was skipped before applying).
    assert stages["APPLIED"] == 3
    # ASSESSMENT: only D went through assessment.
    assert stages["ASSESSMENT"] == 1
    # INTERVIEW: D and E both reached interview (E skipped assessment).
    assert stages["INTERVIEW"] == 2
    assert stages["FINAL_INTERVIEW"] == 1
    assert stages["OFFER"] == 1


async def test_conversion_matches_hand_count(client: httpx.AsyncClient) -> None:
    await _build_fixture(client)

    response = await client.get("/api/v1/dashboard")
    conversion = response.json()["conversion"]

    assert conversion["applied_over_saved"] == 0.75  # 3 applied / 4 eligible saved
    assert round(conversion["assessment_over_applied"], 3) == round(1 / 3, 3)
    assert round(conversion["interview_over_applied"], 3) == round(2 / 3, 3)
    assert conversion["offer_over_interview"] == 0.5  # 1 offer / 2 reached interview
    assert round(conversion["offer_over_applied"], 3) == round(1 / 3, 3)


async def test_duplicate_job_excluded_from_kpis(client: httpx.AsyncClient) -> None:
    await _build_fixture(client)

    response = await client.get("/api/v1/dashboard")
    kpis = response.json()["kpis"]

    # 5 distinct jobs captured (A-E); F is flagged as a duplicate of A and
    # must not inflate the count.
    assert kpis["saved"] == 5


async def test_multi_round_interview_is_one_job_not_two(client: httpx.AsyncClient) -> None:
    """D and E both reached INTERVIEW; E did so via two INTERVIEW_RECEIVED
    events. The funnel must still show 2, not 3 (docs/10 D5)."""
    await _build_fixture(client)

    response = await client.get("/api/v1/analytics/funnel")
    stages = {s["stage"]: s["count"] for s in response.json()}

    assert stages["INTERVIEW"] == 2


async def test_backlog_matches_hand_count(client: httpx.AsyncClient) -> None:
    await _build_fixture(client)

    response = await client.get("/api/v1/dashboard")
    backlog = response.json()["backlog"]

    # Only A is SAVED with no CV generated; B is SKIPPED (excluded from this
    # count by definition -- docs/10 §6 scopes it to SAVED/READY_TO_APPLY).
    assert backlog["jobs_without_cv"] == 1
    assert backlog["cv_ready_not_applied"] == 0
    assert backlog["partial_captures"] == 0


async def test_action_queue_links_reproduce_their_own_counts(client: httpx.AsyncClient) -> None:
    await _build_fixture(client)

    dashboard = (await client.get("/api/v1/dashboard")).json()

    for item in dashboard["action_queue"]:
        # `href` is a web-app path (docs/05 §8: consumed by the SvelteKit
        # Job Inbox, not the raw API) -- prepend the API prefix to hit the
        # same backend route the frontend's /jobs page would call.
        backend_path = "/api/v1" + item["href"]
        listing = await client.get(backend_path)
        assert listing.status_code == 200, item["label"]
        assert len(listing.json()["items"]) == item["count"], item["label"]


async def test_trends_endpoint_returns_a_bucket_covering_today(client: httpx.AsyncClient) -> None:
    await _build_fixture(client)

    response = await client.get("/api/v1/analytics/trends", params={"granularity": "week"})

    assert response.status_code == 200
    points = response.json()
    assert len(points) >= 1
    assert sum(p["saved"] for p in points) == 5


async def test_sources_and_roles_do_not_error_with_unclassified_data(
    client: httpx.AsyncClient,
) -> None:
    await _build_fixture(client)

    sources = await client.get("/api/v1/analytics/sources")
    roles = await client.get("/api/v1/analytics/roles")

    assert sources.status_code == 200
    assert sum(s["saved"] for s in sources.json()) == 5
    assert roles.status_code == 200
    assert roles.json()[0]["name"] == "unclassified"
    assert roles.json()[0]["saved"] == 5


async def test_skills_endpoint_is_honest_about_not_being_built_yet(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/analytics/skills")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert "job_parser" in response.json()["note"]


async def test_dashboard_carries_the_sample_disclosure(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard")

    assert "captured-job sample" in response.json()["sample_note"]
