"""Integration tests for the career profile fact store (FR-005).

`career_achievements` is the table Milestone 3's CV grounding will cite by ID,
so its constraints (single-parent, verified-metric) are tested at the API
boundary here -- they must hold before any generator is built on top of them.
"""

from __future__ import annotations

import httpx


async def test_profile_is_seeded_and_singular(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/career-profile")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["experiences"] == []
    assert body["application_profile"] == {
        "notice_period": None,
        "salary_expectation": None,
        "work_authorization": None,
        "relocation_ok": None,
        "preferred_location": None,
        "links": {},
    }


async def test_patch_profile_summary(client: httpx.AsyncClient) -> None:
    response = await client.patch("/api/v1/career-profile", json={"summary": "MLOps engineer"})

    assert response.status_code == 200
    assert response.json()["summary"] == "MLOps engineer"


async def test_add_experience_and_see_it_in_profile(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/v1/career-profile/experiences",
        json={
            "company": "Acme Corp",
            "title": "ML Engineer",
            "start_date": "2022-01-01",
            "is_current": True,
        },
    )
    assert created.status_code == 201
    exp_id = created.json()["id"]

    profile = await client.get("/api/v1/career-profile")
    companies = [e["company"] for e in profile.json()["experiences"]]
    assert "Acme Corp" in companies

    patched = await client.patch(
        f"/api/v1/career-profile/experiences/{exp_id}", json={"title": "Senior ML Engineer"}
    )
    assert patched.json()["title"] == "Senior ML Engineer"

    deleted = await client.delete(f"/api/v1/career-profile/experiences/{exp_id}")
    assert deleted.status_code == 204

    profile_after = await client.get("/api/v1/career-profile")
    assert profile_after.json()["experiences"] == []


async def test_achievement_requires_verified_metric_to_have_a_value(
    client: httpx.AsyncClient,
) -> None:
    """Backed by a DB CHECK constraint (docs/04 §3), but caught in the service
    layer first so the API returns a clean 422, not a raw 500."""
    response = await client.post(
        "/api/v1/career-profile/achievements",
        json={
            "statement": "Reduced latency significantly",
            "metric_value": "70% faster",
            "metric_verified": True,
        },
    )
    assert response.status_code == 201  # metric_value present -> rule satisfied

    unverified = await client.post(
        "/api/v1/career-profile/achievements",
        json={"statement": "Improved something", "metric_verified": True, "metric_value": None},
    )
    assert unverified.status_code == 422
    assert unverified.json()["error_type"] == "VALIDATION_FAILED"


async def test_achievement_cannot_belong_to_both_experience_and_project(
    client: httpx.AsyncClient,
) -> None:
    exp = await client.post(
        "/api/v1/career-profile/experiences",
        json={"company": "Acme", "title": "Engineer", "start_date": "2022-01-01"},
    )
    project = await client.post("/api/v1/career-profile/projects", json={"name": "Side project"})

    response = await client.post(
        "/api/v1/career-profile/achievements",
        json={
            "statement": "Did a thing",
            "experience_id": exp.json()["id"],
            "project_id": project.json()["id"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "VALIDATION_FAILED"


async def test_achievement_with_tags_round_trips(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/v1/career-profile/achievements",
        json={
            "statement": "Built the capture pipeline",
            "skill_tags": ["python", "fastapi"],
            "technology_tags": ["postgresql"],
        },
    )
    assert created.status_code == 201
    assert created.json()["skill_tags"] == ["python", "fastapi"]

    profile = await client.get("/api/v1/career-profile")
    achievement = next(a for a in profile.json()["achievements"] if a["id"] == created.json()["id"])
    assert achievement["technology_tags"] == ["postgresql"]


async def test_delete_achievement_is_soft_delete(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/v1/career-profile/achievements", json={"statement": "Something"}
    )
    achievement_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/career-profile/achievements/{achievement_id}")
    assert deleted.status_code == 204

    profile = await client.get("/api/v1/career-profile")
    ids = [a["id"] for a in profile.json()["achievements"]]
    assert achievement_id not in ids


async def test_application_profile_patch(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/career-profile/application-profile",
        json={"notice_period": "1 month", "relocation_ok": False},
    )

    assert response.status_code == 200
    assert response.json()["notice_period"] == "1 month"
    assert response.json()["relocation_ok"] is False


async def test_skill_education_certification_crud(client: httpx.AsyncClient) -> None:
    skill = await client.post(
        "/api/v1/career-profile/skills", json={"name": "Python", "years_experience": 5}
    )
    education = await client.post(
        "/api/v1/career-profile/education", json={"institution": "ITB", "degree": "BSc"}
    )
    certification = await client.post(
        "/api/v1/career-profile/certifications", json={"name": "AWS ML Specialty"}
    )

    assert skill.status_code == 201
    assert education.status_code == 201
    assert certification.status_code == 201

    profile = await client.get("/api/v1/career-profile")
    body = profile.json()
    assert body["skills"][0]["name"] == "Python"
    assert body["education"][0]["institution"] == "ITB"
    assert body["certifications"][0]["name"] == "AWS ML Specialty"
