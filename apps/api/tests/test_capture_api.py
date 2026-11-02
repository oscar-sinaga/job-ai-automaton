"""Integration tests for POST /api/v1/jobs/capture and enrichment.

These guard the product's core reliability promise (NFR-002, FR-001..FR-003):
capture always succeeds and preserves raw data, even for partial mobile shares,
and a retry can never create a duplicate job.
"""

from __future__ import annotations

import datetime as dt

import httpx

LONG_JD = "We are looking for a Senior ML Engineer. " * 10


def _envelope(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "url": "https://www.linkedin.com/jobs/view/4012345678/?utm_source=share",
        "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        "capture_method": "extension",
        "source_hint": "linkedin.com",
        "page_title": "Senior ML Engineer - Acme",
        "raw_text": LONG_JD,
    }
    payload.update(overrides)
    return payload


async def test_capture_requires_api_key(client: httpx.AsyncClient) -> None:
    client.headers.pop("X-API-Key")
    response = await client.post("/api/v1/jobs/capture", json=_envelope())
    assert response.status_code == 401
    assert response.json()["error_type"] == "UNAUTHORIZED"


async def test_capture_from_extension_is_complete(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/jobs/capture", json=_envelope())

    assert response.status_code == 201
    body = response.json()
    assert body["ref"].startswith("J")
    assert body["capture_completeness"] == "CAPTURED_COMPLETE"
    assert body["duplicate_of_job_id"] is None
    assert body["created"] is True


async def test_mobile_share_with_only_url_and_title_saves_as_partial(
    client: httpx.AsyncClient,
) -> None:
    envelope = _envelope(
        capture_method="mobile_share",
        raw_text=None,
        url="https://www.jobstreet.co.id/job/999999",
    )
    response = await client.post("/api/v1/jobs/capture", json=envelope)

    assert response.status_code == 201
    assert response.json()["capture_completeness"] == "CAPTURED_PARTIAL"


async def test_capture_uses_job_metadata_and_preserves_original_page_title(
    client: httpx.AsyncClient,
) -> None:
    envelope = _envelope(job_title="  Master Data Engineer  ", company_name="Fitch Group")
    capture = await client.post("/api/v1/jobs/capture", json=envelope)
    detail = (await client.get(f"/api/v1/jobs/{capture.json()['job_id']}")).json()

    assert detail["title"] == "Master Data Engineer"
    assert detail["company"] == "Fitch Group"
    assert detail["snapshots"][0]["page_title"] == envelope["page_title"]


async def test_capture_without_job_metadata_keeps_page_title(
    client: httpx.AsyncClient,
) -> None:
    capture = await client.post(
        "/api/v1/jobs/capture", json=_envelope(job_title="  ", company_name="  ")
    )
    detail = (await client.get(f"/api/v1/jobs/{capture.json()['job_id']}")).json()

    assert detail["title"] == "Senior ML Engineer - Acme"
    assert detail["company"] is None


async def test_manual_url_with_no_text_needs_enrichment(client: httpx.AsyncClient) -> None:
    envelope = _envelope(capture_method="manual_url", raw_text=None)
    response = await client.post("/api/v1/jobs/capture", json=envelope)

    assert response.status_code == 201
    assert response.json()["capture_completeness"] == "NEEDS_ENRICHMENT"


async def test_raw_text_is_preserved_verbatim(client: httpx.AsyncClient) -> None:
    capture = await client.post("/api/v1/jobs/capture", json=_envelope())
    job_id = capture.json()["job_id"]

    raw = await client.get(f"/api/v1/jobs/{job_id}/raw")

    assert raw.status_code == 200
    assert raw.json()["raw_text"] == LONG_JD


async def test_idempotency_key_replay_returns_same_job(client: httpx.AsyncClient) -> None:
    key = "11111111-1111-1111-1111-111111111111"

    first = await client.post(
        "/api/v1/jobs/capture", json=_envelope(), headers={"Idempotency-Key": key}
    )
    second = await client.post(
        "/api/v1/jobs/capture", json=_envelope(), headers={"Idempotency-Key": key}
    )

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["job_id"] == first.json()["job_id"]

    listing = await client.get("/api/v1/jobs")
    assert listing.json()["items"] and len(listing.json()["items"]) == 1


async def test_duplicate_url_is_flagged_not_blocked(client: httpx.AsyncClient) -> None:
    first = await client.post("/api/v1/jobs/capture", json=_envelope())
    second = await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(url="https://www.linkedin.com/jobs/view/4012345678/?utm_source=app"),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["job_id"] != first.json()["job_id"]
    assert second.json()["duplicate_of_job_id"] == first.json()["job_id"]

    listing = await client.get("/api/v1/jobs")
    assert len(listing.json()["items"]) == 2


async def test_enrichment_adds_snapshot_without_touching_the_first(
    client: httpx.AsyncClient,
) -> None:
    capture = await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(capture_method="manual_url", raw_text=None),
    )
    job_id = capture.json()["job_id"]
    assert capture.json()["capture_completeness"] == "NEEDS_ENRICHMENT"

    original_raw = await client.get(f"/api/v1/jobs/{job_id}/raw")
    assert original_raw.json()["raw_text"] is None

    enrichment = await client.post(
        f"/api/v1/jobs/{job_id}/snapshots",
        json={
            "raw_text": LONG_JD,
            "capture_method": "paste_text",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    )
    assert enrichment.status_code == 201
    assert enrichment.json()["capture_completeness"] == "CAPTURED_COMPLETE"

    detail = await client.get(f"/api/v1/jobs/{job_id}")
    assert len(detail.json()["snapshots"]) == 2
    assert detail.json()["capture_completeness"] == "CAPTURED_COMPLETE"

    # The first snapshot itself is never mutated (FR-003) -- fetch it directly
    # via its own capture record: the /raw endpoint now serves the LATEST
    # snapshot, so we assert byte-identity by re-reading job detail metadata.
    first_snapshot_meta = detail.json()["snapshots"][0]
    assert first_snapshot_meta["capture_method"] == "manual_url"
    assert first_snapshot_meta["raw_text_length"] == 0


async def test_capture_writes_a_job_saved_event(client: httpx.AsyncClient) -> None:
    capture = await client.post("/api/v1/jobs/capture", json=_envelope())
    job_id = capture.json()["job_id"]

    detail = await client.get(f"/api/v1/jobs/{job_id}")

    event_types = [e["event_type"] for e in detail.json()["events"]]
    assert event_types == ["JOB_SAVED"]


async def test_verification_page_saves_only_link_and_can_be_enriched(
    client: httpx.AsyncClient,
) -> None:
    capture = await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(
            page_title="Just a moment...",
            job_title="Incorrect challenge title",
            company_name="Cloudflare",
            raw_text="Performing security verification. Performance and Security by Cloudflare.",
        ),
    )
    assert capture.status_code == 201
    job_id = capture.json()["job_id"]
    assert capture.json()["capture_completeness"] == "NEEDS_ENRICHMENT"
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert detail["title"] is None
    assert detail["company"] is None
    assert detail["snapshots"][0]["page_title"] == "Just a moment..."
    assert (await client.get(f"/api/v1/jobs/{job_id}/raw")).json()["raw_text"] is None

    blocked_paste = await client.post(
        f"/api/v1/jobs/{job_id}/snapshots",
        json={
            "raw_text": "Performing security verification. Performance and Security by Cloudflare.",
            "capture_method": "paste_text",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    )
    assert blocked_paste.status_code == 422
    assert len((await client.get(f"/api/v1/jobs/{job_id}")).json()["snapshots"]) == 1

    enriched = await client.post(
        f"/api/v1/jobs/{job_id}/snapshots",
        json={
            "raw_text": LONG_JD,
            "capture_method": "paste_text",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    )
    assert enriched.status_code == 201
    assert enriched.json()["capture_completeness"] == "CAPTURED_COMPLETE"
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert len(detail["snapshots"]) == 2
    assert detail["snapshots"][0]["raw_text_length"] == 0
    assert (await client.get(f"/api/v1/jobs/{job_id}/raw")).json()["raw_text"] == LONG_JD


async def test_login_capture_omits_page_text(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(metadata={"page_access": "login_required"}, page_title="Sign in"),
    )
    assert response.status_code == 201
    assert response.json()["capture_completeness"] == "NEEDS_ENRICHMENT"
    job_id = response.json()["job_id"]
    assert (await client.get(f"/api/v1/jobs/{job_id}/raw")).json()["raw_text"] is None


async def test_job_mentioning_cloudflare_is_still_captured(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(
            page_title="Cloudflare Security Engineer",
            job_title="Security Engineer",
            raw_text="Build Cloudflare verify you are human widgets and SQL pipelines. " * 10,
            metadata={"page_access": {"unknown": True}},
        ),
    )
    assert response.status_code == 201
    assert response.json()["capture_completeness"] == "CAPTURED_COMPLETE"
