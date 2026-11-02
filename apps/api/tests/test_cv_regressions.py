"""Regressions from the first real-usage readiness review."""

import datetime as dt

import httpx
import pytest

from oscar_api.modules.cv.grounding import GroundingContext, verify_bullet, verify_draft
from oscar_api.modules.cv.models import CVVersion
from oscar_api.modules.cv.pdf import render_pdf
from oscar_api.modules.cv.schemas import CVDraft, DraftBullet, DraftExperienceBlock
from test_cv_api import _good_draft, _setup_job_and_profile
from test_grounding import _achievement, _profile_with


def test_existing_fact_id_does_not_validate_an_unrelated_claim():
    fact = _achievement(1, statement="Built internal reports.")
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(text="Won the Nobel Prize.", supporting_fact_ids=["ach_1"])
    assert verify_bullet(bullet, ctx) == "UNSUPPORTED_CLAIM"


def test_appending_an_invention_to_a_real_statement_is_rejected():
    fact = _achievement(1, statement="Built internal reports.")
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="Built internal reports. Won the Nobel Prize.", supporting_fact_ids=["ach_1"]
    )
    assert verify_bullet(bullet, ctx) == "UNSUPPORTED_CLAIM"


def test_unsupported_skills_are_removed_and_reported():
    fact = _achievement(1, statement="Built reports.", technology_tags=["python"])
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    draft = CVDraft(
        summary=DraftBullet(text=fact.statement, supporting_fact_ids=["ach_1"]),
        skills=["Python", "Kubernetes", "Quantum Computing"],
    )
    cleaned, report = verify_draft(draft, ctx)
    assert cleaned.skills == ["Python"]
    assert [r.reason for r in report.rejections] == ["UNSUPPORTED_SKILL"] * 2


@pytest.mark.parametrize("statement", ["Built Django services.", "Used JavaScript."])
def test_technology_names_do_not_match_inside_other_names(statement):
    fact = _achievement(1, statement=statement, technology_tags=["django", "javascript"])
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    assert verify_bullet(DraftBullet(text=statement, supporting_fact_ids=["ach_1"]), ctx) is None


def test_pdf_handles_multiple_bullets_and_unicode():
    version = CVVersion(
        job_id=1,
        version_number=1,
        sections={
            "summary": {"text": "Engineer — data → delivery."},
            "experience": [
                {"bullets": [{"text": "Built reports."}, {"text": "Improved delivery."}]}
            ],
            "projects": [
                {"bullets": [{"text": "Tested • pipelines."}, {"text": "Shipped tools."}]}
            ],
            "skills": ["Python"],
        },
    )
    assert render_pdf(version).startswith(b"%PDF")


async def _generate(client: httpx.AsyncClient, fake_llm) -> tuple[int, int]:
    job_id, fact_id, experience_id = await _setup_job_and_profile(client)
    fake_llm.queue(_good_draft(f"ach_{fact_id}", experience_id))
    response = await client.post(f"/api/v1/jobs/{job_id}/generate-cv", json={})
    assert response.status_code == 201, response.text
    return job_id, response.json()["cv_version_id"]


async def test_approving_after_application_preserves_status(client, fake_llm):
    job_id, cv_id = await _generate(client, fake_llm)
    applied = await client.post("/api/v1/applications", json={"job_id": job_id})
    assert applied.status_code == 201
    approved = await client.post(f"/api/v1/cv/{cv_id}/approve")
    assert approved.status_code == 200
    job = await client.get(f"/api/v1/jobs/{job_id}")
    assert job.json()["current_status"] == "APPLIED"


async def test_export_requires_review_and_download_returns_the_saved_pdf(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    unreviewed = await client.post(f"/api/v1/cv/{cv_id}/export")
    assert unreviewed.status_code == 409
    approved = await client.post(f"/api/v1/cv/{cv_id}/approve")
    assert approved.status_code == 200
    exported = await client.post(f"/api/v1/cv/{cv_id}/export")
    assert exported.status_code == 201
    artifact_id = exported.json()["artifact_id"]
    download = await client.get(f"/api/v1/cv/{cv_id}/artifacts/{artifact_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="CV_J' in download.headers["content-disposition"]
    assert download.content.startswith(b"%PDF")
    missing = await client.get(f"/api/v1/cv/{cv_id + 1}/artifacts/{artifact_id}/download")
    assert missing.status_code == 404
    unauthorized = await client.get(
        f"/api/v1/cv/{cv_id}/artifacts/{artifact_id}/download", headers={"X-API-Key": "wrong"}
    )
    assert unauthorized.status_code == 401


async def test_edit_cannot_introduce_unsupported_claims_or_skills(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    original = (await client.get(f"/api/v1/cv/{cv_id}")).json()["sections"]
    bad_skills = await client.patch(
        f"/api/v1/cv/{cv_id}", json={"sections": {**original, "skills": ["Quantum Computing"]}}
    )
    assert bad_skills.status_code == 422
    original["summary"]["text"] = "Won the Nobel Prize."
    bad_claim = await client.patch(f"/api/v1/cv/{cv_id}", json={"sections": original})
    assert bad_claim.status_code == 422


async def test_malformed_edit_is_validation_error(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    response = await client.patch(f"/api/v1/cv/{cv_id}", json={"sections": {"skills": 42}})
    assert response.status_code == 422


async def test_cv_keeps_source_text_and_experience_details(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    sections = (await client.get(f"/api/v1/cv/{cv_id}")).json()["sections"]
    assert (
        next(iter(sections["source_facts"].values()))
        == "Built production ML pipelines using Python"
    )
    block = sections["experience"][0]
    assert block["company"] == "Acme Corp"
    assert block["title"] == "ML Engineer"
    assert dt.date.fromisoformat(block["start_date"]) == dt.date(2022, 1, 1)


def test_fact_cannot_be_assigned_to_an_unrelated_experience():
    from test_grounding import _experience

    exp = _experience(1)
    fact = _achievement(1, statement="Built reports.", experience=exp)
    ctx = GroundingContext.build(_profile_with(experiences=[exp], achievements=[fact]), [fact])
    draft = CVDraft(
        summary=DraftBullet(text="", supporting_fact_ids=[]),
        experience=[
            DraftExperienceBlock(
                experience_id=2,
                bullets=[DraftBullet(text=fact.statement, supporting_fact_ids=["ach_1"])],
            )
        ],
    )
    cleaned, report = verify_draft(draft, ctx)
    assert cleaned.experience == []
    assert report.rejections[0].reason == "FACT_PARENT_MISMATCH"


async def test_new_version_does_not_inherit_approval_and_sources_are_immutable(client, fake_llm):
    job_id, cv_id = await _generate(client, fake_llm)
    await client.post(f"/api/v1/cv/{cv_id}/approve")
    original = (await client.get(f"/api/v1/cv/{cv_id}")).json()
    edited = await client.patch(f"/api/v1/cv/{cv_id}", json={"sections": original["sections"]})
    assert edited.status_code == 200
    assert edited.json()["is_approved"] is False
    assert (await client.post(f"/api/v1/cv/{edited.json()['id']}/export")).status_code == 409
    profile = (await client.get("/api/v1/career-profile")).json()
    fact_id = profile["achievements"][0]["id"]
    await client.patch(
        f"/api/v1/career-profile/achievements/{fact_id}", json={"statement": "Updated fact text"}
    )
    unchanged = (await client.get(f"/api/v1/cv/{cv_id}")).json()
    assert unchanged["sections"] == original["sections"]
    assert unchanged["job_id"] == job_id


async def test_cv_pdf_keeps_contact_details_from_its_version(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    await client.patch(
        "/api/v1/career-profile/application-profile",
        json={"links": {"cv_name": "Changed Name", "cv_email": "changed@example.com"}},
    )
    original = (await client.get(f"/api/v1/cv/{cv_id}")).json()
    assert original["sections"]["candidate"]["name"] == "Sample Candidate"
    await client.post(f"/api/v1/cv/{cv_id}/approve")
    assert (await client.post(f"/api/v1/cv/{cv_id}/export")).status_code == 201


async def test_missing_contact_details_prevent_export(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    await client.patch("/api/v1/career-profile/application-profile", json={"links": {}})
    original = (await client.get(f"/api/v1/cv/{cv_id}")).json()
    edited = await client.patch(f"/api/v1/cv/{cv_id}", json={"sections": original["sections"]})
    new_id = edited.json()["id"]
    await client.post(f"/api/v1/cv/{new_id}/approve")
    response = await client.post(f"/api/v1/cv/{new_id}/export")
    assert response.status_code == 422
    assert "Career Profile" in response.json()["message"]


async def test_reexport_keeps_the_exact_original_file_after_profile_changes(client, fake_llm):
    _, cv_id = await _generate(client, fake_llm)
    await client.post(f"/api/v1/cv/{cv_id}/approve")
    first = (await client.post(f"/api/v1/cv/{cv_id}/export")).json()
    original_pdf = (await client.get(first["download_url"])).content
    profile = (await client.get("/api/v1/career-profile")).json()
    fact_id = profile["achievements"][0]["id"]
    await client.patch(
        f"/api/v1/career-profile/achievements/{fact_id}", json={"statement": "Changed career fact"}
    )
    repeated = await client.post(f"/api/v1/cv/{cv_id}/export")
    assert repeated.status_code == 201
    assert repeated.json()["artifact_id"] == first["artifact_id"]
    assert (await client.get(repeated.json()["download_url"])).content == original_pdf
