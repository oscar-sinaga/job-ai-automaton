"""Integration tests for the Job Inbox surface: list, filter, detail, patch."""

from __future__ import annotations

import datetime as dt

import httpx


def _envelope(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "url": "https://www.linkedin.com/jobs/view/1000000001/",
        "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        "capture_method": "extension",
        "source_hint": "linkedin.com",
        "page_title": "ML Engineer",
        "raw_text": "We need an ML Engineer. " * 10,
    }
    payload.update(overrides)
    return payload


async def test_list_jobs_returns_newest_first(client: httpx.AsyncClient) -> None:
    for i in range(3):
        await client.post(
            "/api/v1/jobs/capture",
            json=_envelope(url=f"https://www.linkedin.com/jobs/view/100000000{i}/"),
        )

    response = await client.get("/api/v1/jobs")

    assert response.status_code == 200
    refs = [item["ref"] for item in response.json()["items"]]
    assert refs == sorted(refs, reverse=True)


async def test_list_jobs_filters_by_status(client: httpx.AsyncClient) -> None:
    await client.post("/api/v1/jobs/capture", json=_envelope())

    saved = await client.get("/api/v1/jobs", params={"status": "SAVED"})
    offered = await client.get("/api/v1/jobs", params={"status": "OFFER"})

    assert len(saved.json()["items"]) == 1
    assert len(offered.json()["items"]) == 0


async def test_list_jobs_filters_by_source(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(
            url="https://www.jobstreet.co.id/job/111111",
            source_hint="jobstreet.co.id",
        ),
    )
    await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(url="https://www.linkedin.com/jobs/view/222222/"),
    )

    linkedin_only = await client.get("/api/v1/jobs", params={"source": "linkedin.com"})

    assert len(linkedin_only.json()["items"]) == 1
    assert linkedin_only.json()["items"][0]["source"] == "linkedin.com"


async def test_list_jobs_search_matches_title(client: httpx.AsyncClient) -> None:
    await client.post("/api/v1/jobs/capture", json=_envelope(page_title="Backend Engineer"))
    await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(
            url="https://www.linkedin.com/jobs/view/333333/", page_title="Data Scientist"
        ),
    )

    results = await client.get("/api/v1/jobs", params={"q": "engineer"})

    assert len(results.json()["items"]) == 1
    assert results.json()["items"][0]["title"] == "Backend Engineer"


async def test_pagination_cursor_walks_all_items(client: httpx.AsyncClient) -> None:
    for i in range(5):
        await client.post(
            "/api/v1/jobs/capture",
            json=_envelope(url=f"https://www.linkedin.com/jobs/view/500000{i}/"),
        )

    seen: list[int] = []
    cursor = None
    for _ in range(10):  # bounded loop; would hang forever on a pagination bug
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = await client.get("/api/v1/jobs", params=params)
        body = page.json()
        seen.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == 5
    assert len(set(seen)) == 5  # no item appears on two pages


async def test_get_job_detail_includes_snapshots_and_events(client: httpx.AsyncClient) -> None:
    capture = await client.post("/api/v1/jobs/capture", json=_envelope())
    job_id = capture.json()["job_id"]

    detail = await client.get(f"/api/v1/jobs/{job_id}")

    assert detail.status_code == 200
    body = detail.json()
    assert body["title"] == "ML Engineer"
    assert len(body["snapshots"]) == 1
    assert body["snapshots"][0]["raw_text_length"] > 0


async def test_get_unknown_job_is_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/jobs/999999")

    assert response.status_code == 404
    assert response.json()["error_type"] == "NOT_FOUND"


async def test_patch_job_corrects_title_and_company(client: httpx.AsyncClient) -> None:
    capture = await client.post("/api/v1/jobs/capture", json=_envelope(page_title="ml engnieer"))
    job_id = capture.json()["job_id"]

    patched = await client.patch(
        f"/api/v1/jobs/{job_id}",
        json={"title": "ML Engineer", "company": "Acme Corp"},
    )

    assert patched.status_code == 200
    assert patched.json()["title"] == "ML Engineer"
    assert patched.json()["company"] == "Acme Corp"

    detail = await client.get(f"/api/v1/jobs/{job_id}")
    event_types = [e["event_type"] for e in detail.json()["events"]]
    assert event_types == ["JOB_SAVED", "JOB_UPDATED"]


async def test_patch_job_reusing_the_same_company_name_reuses_the_row(
    client: httpx.AsyncClient,
) -> None:
    first = await client.post("/api/v1/jobs/capture", json=_envelope())
    second = await client.post(
        "/api/v1/jobs/capture",
        json=_envelope(url="https://www.linkedin.com/jobs/view/777777/"),
    )

    await client.patch(f"/api/v1/jobs/{first.json()['job_id']}", json={"company": "Acme Corp"})
    await client.patch(f"/api/v1/jobs/{second.json()['job_id']}", json={"company": "acme corp"})

    listing = await client.get("/api/v1/jobs")
    companies = {item["company"] for item in listing.json()["items"]}
    assert companies == {"Acme Corp"}
