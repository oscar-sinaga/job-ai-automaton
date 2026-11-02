"""Integration tests for CV generation, review, and export (FR-006/FR-007).

Uses `fake_llm`/`fake_storage` throughout -- no test calls a real model or
touches the real filesystem (docs/12 §2).
"""

from __future__ import annotations

import datetime as dt

import httpx

from fakes import FailingLLMProvider
from oscar_api.main import app
from oscar_api.modules.cv.deps import get_llm_provider

LONG_JD = "We are hiring a Senior ML Engineer with strong Python experience. " * 5


async def _setup_job_and_profile(client: httpx.AsyncClient) -> tuple[int, int, int]:
    """Returns (job_id, achievement_id, experience_id)."""
    capture = await client.post(
        "/api/v1/jobs/capture",
        json={
            "url": "https://example.com/jobs/1",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
            "capture_method": "extension",
            "page_title": "Senior ML Engineer",
            "raw_text": LONG_JD,
        },
    )
    job_id = capture.json()["job_id"]

    exp = await client.post(
        "/api/v1/career-profile/experiences",
        json={
            "company": "Acme Corp",
            "title": "ML Engineer",
            "start_date": "2022-01-01",
            "is_current": True,
        },
    )
    exp_id = exp.json()["id"]

    achievement = await client.post(
        "/api/v1/career-profile/achievements",
        json={
            "statement": "Built production ML pipelines using Python",
            "experience_id": exp_id,
            "skill_tags": ["python"],
        },
    )
    contact = await client.patch(
        "/api/v1/career-profile/application-profile",
        json={"links": {"cv_name": "Sample Candidate", "cv_email": "sample@example.com"}},
    )
    assert contact.status_code == 200
    return job_id, achievement.json()["id"], exp_id


def _good_draft(fact_id: str, experience_id: int) -> dict:
    return {
        "summary": {
            "text": "Built production ML pipelines using Python.",
            "supporting_fact_ids": [fact_id],
        },
        "experience": [
            {
                "experience_id": experience_id,
                "bullets": [
                    {
                        "text": "Built production ML pipelines using Python.",
                        "supporting_fact_ids": [fact_id],
                    }
                ],
            }
        ],
        "projects": [],
        "skills": ["Python"],
        "missing_requirements": ["Kubernetes (not in profile)"],
    }


async def test_generate_cv_succeeds_with_grounded_draft(
    client: httpx.AsyncClient, fake_llm
) -> None:
    job_id, achievement_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{achievement_id}", experience_id))

    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["label"] == f"CV_J{job_id:03d}_v1"
    assert body["grounding_report"]["claims_rejected"] == 0
    assert body["missing_requirements"] == ["Kubernetes (not in profile)"]
    assert body["sections"]["summary"]["supporting_fact_ids"] == [f"ach_{achievement_id}"]


async def test_generate_cv_drops_fabricated_bullet_but_keeps_grounded_content(
    client: httpx.AsyncClient, fake_llm
) -> None:
    job_id, achievement_id, experience_id = await _setup_job_and_profile(client)
    draft = _good_draft(f"ach_{achievement_id}", experience_id)
    draft["experience"][0]["bullets"].append(
        {"text": "Led a team of 12 engineers.", "supporting_fact_ids": []}
    )
    fake_llm.queue(draft)

    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["grounding_report"]["claims_rejected"] == 1
    assert body["grounding_report"]["rejections"][0]["reason"] == "NO_SUPPORTING_FACT"
    bullets = body["sections"]["experience"][0]["bullets"]
    assert len(bullets) == 1
    assert "Led a team" not in bullets[0]["text"]


async def test_generate_cv_all_rejected_persists_no_version(
    client: httpx.AsyncClient, fake_llm
) -> None:
    job_id, _, _ = await _setup_job_and_profile(client)
    fake_llm.queue(
        {
            "summary": {"text": "Fabricated claim.", "supporting_fact_ids": []},
            "experience": [],
            "projects": [],
        }
    )

    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})

    assert response.status_code == 422
    assert response.json()["error_type"] == "GROUNDING_FAILED"

    versions = await client.get(f"/api/v1/jobs/{job_id}/cv-versions")
    assert versions.json() == []


async def test_generate_cv_without_raw_jd_text_is_validation_error(
    client: httpx.AsyncClient, fake_llm
) -> None:
    capture = await client.post(
        "/api/v1/jobs/capture",
        json={
            "url": "https://example.com/jobs/2",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
            "capture_method": "manual_url",
        },
    )
    job_id = capture.json()["job_id"]

    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})

    assert response.status_code == 422
    assert response.json()["error_type"] == "VALIDATION_FAILED"
    assert fake_llm.calls == []  # never even called the model


async def test_generate_cv_rejects_partial_shared_text_before_calling_model(
    client: httpx.AsyncClient, fake_llm
) -> None:
    url = "https://example.com/jobs/shared-link-only"
    capture = await client.post(
        "/api/v1/jobs/capture",
        json={
            "url": url,
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
            "capture_method": "mobile_share",
            "page_title": "Data Engineer",
            "shared_text": f"Data Engineer\n{url}",
        },
    )
    assert capture.json()["capture_completeness"] == "CAPTURED_PARTIAL"
    job_id = capture.json()["job_id"]
    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    assert response.status_code == 422
    assert response.json()["error_type"] == "VALIDATION_FAILED"
    assert "full job description" in response.json()["message"]
    assert fake_llm.calls == []
    assert (await client.get(f"/api/v1/jobs/{job_id}/cv-versions")).json() == []


async def test_generate_cv_when_provider_times_out_is_llm_unavailable(
    client: httpx.AsyncClient,
) -> None:
    job_id, _, _ = await _setup_job_and_profile(client)
    app.dependency_overrides[get_llm_provider] = lambda: FailingLLMProvider()
    try:
        response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    finally:
        del app.dependency_overrides[get_llm_provider]

    assert response.status_code == 503
    assert response.json()["error_type"] == "LLM_UNAVAILABLE"

    versions = await client.get(f"/api/v1/jobs/{job_id}/cv-versions")
    assert versions.json() == []


async def test_edit_creates_new_version_and_keeps_the_original(
    client: httpx.AsyncClient, fake_llm
) -> None:
    job_id, achievement_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{achievement_id}", experience_id))
    generated = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    cv_id = generated.json()["cv_version_id"]
    original_sections = generated.json()["sections"]

    edited = await client.patch(
        f"/api/v1/cv/{cv_id}",
        json={
            "sections": {**original_sections, "summary": {"text": "", "supporting_fact_ids": []}}
        },
    )

    assert edited.status_code == 200
    assert edited.json()["version_number"] == 2
    assert edited.json()["sections"]["summary"]["text"] == ""

    original = await client.get(f"/api/v1/cv/{cv_id}")
    assert original.json()["sections"]["skills"] == ["Python"]  # untouched


async def test_approve_sets_job_ready_to_apply(client: httpx.AsyncClient, fake_llm) -> None:
    job_id, achievement_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{achievement_id}", experience_id))
    generated = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    cv_id = generated.json()["cv_version_id"]

    approved = await client.post(f"/api/v1/cv/{cv_id}/approve")
    assert approved.status_code == 200

    job = await client.get(f"/api/v1/jobs/{job_id}")
    assert job.json()["current_status"] == "READY_TO_APPLY"
    event_types = [e["event_type"] for e in job.json()["events"]]
    assert "CV_APPROVED" in event_types


async def test_export_creates_a_pdf_artifact(
    client: httpx.AsyncClient, fake_llm, fake_storage
) -> None:
    job_id, achievement_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{achievement_id}", experience_id))
    generated = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    cv_id = generated.json()["cv_version_id"]

    await client.post(f"/api/v1/cv/{cv_id}/approve")
    exported = await client.post(f"/api/v1/cv/{cv_id}/export")

    assert exported.status_code == 201
    uri = exported.json()["storage_uri"]
    assert uri.startswith("memory://")
    assert fake_storage.load(uri)[:4] == b"%PDF"


async def test_mark_submitted_is_exclusive_per_job(client: httpx.AsyncClient, fake_llm) -> None:
    job_id, achievement_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{achievement_id}", experience_id))
    v1 = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    cv1_id = v1.json()["cv_version_id"]

    fake_llm.queue(_good_draft(f"ach_{achievement_id}", experience_id))
    v2 = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    cv2_id = v2.json()["cv_version_id"]

    await client.post(f"/api/v1/cv/{cv1_id}/mark-submitted")
    second = await client.post(f"/api/v1/cv/{cv2_id}/mark-submitted")

    assert second.json()["is_submitted"] is True
    first_now = await client.get(f"/api/v1/cv/{cv1_id}")
    assert first_now.json()["is_submitted"] is False


async def test_missing_ai_key_returns_actionable_503(
    client: httpx.AsyncClient, monkeypatch
) -> None:
    from oscar_api.config import get_settings

    job_id, _, _ = await _setup_job_and_profile(client)
    app.dependency_overrides.pop(get_llm_provider)
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    assert response.status_code == 503
    assert response.json()["error_type"] == "LLM_UNAVAILABLE"
    assert "not configured" in response.json()["message"]
    assert (await client.get(f"/api/v1/jobs/{job_id}")).status_code == 200
