"""Unit tests for the grounding verifier (docs/07 §3) -- the mechanism G3
("zero fabricated claims", docs/01 §5) depends on. Built entirely from
in-memory, unpersisted ORM objects -- no database needed, matching how
docs/12 §3 frames this as the project's highest-value unit-test suite.
"""

from __future__ import annotations

import datetime as dt

from oscar_api.modules.career.models import (
    CareerAchievement,
    CareerExperience,
    CareerProfile,
    CareerSkill,
)
from oscar_api.modules.cv.grounding import GroundingContext, fact_id_of, verify_bullet, verify_draft
from oscar_api.modules.cv.schemas import CVDraft, DraftBullet, DraftExperienceBlock


def _profile_with(
    *, experiences=None, projects=None, achievements=None, skills=None
) -> CareerProfile:
    profile = CareerProfile(id=1, user_id=1)
    profile.experiences = experiences or []
    profile.projects = projects or []
    profile.achievements = achievements or []
    profile.skills = skills or []
    return profile


def _experience(
    id_: int, *, company="Acme Corp", title="ML Engineer", years_ago=2, is_current=True, months=12
) -> CareerExperience:
    today = dt.date.today()
    start = dt.date(today.year - years_ago, today.month, today.day)
    exp = CareerExperience(
        id=id_, company=company, title=title, start_date=start, is_current=is_current
    )
    if not is_current:
        exp.end_date = start + dt.timedelta(days=months * 30)
    return exp


def _achievement(
    id_: int,
    *,
    statement="Did something",
    experience=None,
    project=None,
    metric_value=None,
    metric_verified=False,
    skill_tags=None,
    technology_tags=None,
    domain_tags=None,
    verification_status="unverified",
) -> CareerAchievement:
    a = CareerAchievement(
        id=id_,
        statement=statement,
        metric_value=metric_value,
        metric_verified=metric_verified,
        skill_tags=skill_tags or [],
        technology_tags=technology_tags or [],
        domain_tags=domain_tags or [],
        verification_status=verification_status,
    )
    a.experience = experience
    a.project = project
    return a


def test_bullet_passes_when_it_cites_a_retrieved_fact():
    exp = _experience(7)
    fact = _achievement(
        41, statement="Built things in Python.", experience=exp, skill_tags=["python"]
    )
    profile = _profile_with(experiences=[exp], achievements=[fact])
    ctx = GroundingContext.build(profile, [fact])

    bullet = DraftBullet(text="Built things in Python.", supporting_fact_ids=[fact_id_of(fact)])

    assert verify_bullet(bullet, ctx) is None


def test_v1_rejects_bullet_with_no_supporting_facts():
    ctx = GroundingContext.build(_profile_with(), [])
    bullet = DraftBullet(text="Did something impressive.", supporting_fact_ids=[])

    assert verify_bullet(bullet, ctx) == "NO_SUPPORTING_FACT"


def test_v1_rejects_fact_id_not_in_retrieved_set():
    """A fact_id that exists in the DB but was never given to the model is
    treated as fabrication (docs/07 §3), not looked up against the whole DB."""
    ctx = GroundingContext.build(_profile_with(), [])  # nothing retrieved
    bullet = DraftBullet(text="Something.", supporting_fact_ids=["ach_999"])

    assert verify_bullet(bullet, ctx) == "FACT_NOT_RETRIEVED"


def test_v2_rejects_invented_number():
    fact = _achievement(
        1,
        statement="Reduced latency from 320ms to 90ms.",
        metric_value="reduced latency from 320ms to 90ms",
        metric_verified=True,
    )
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(text="Reduced latency by 70%.", supporting_fact_ids=[fact_id_of(fact)])

    assert verify_bullet(bullet, ctx) == "METRIC_MISMATCH"


def test_v2_accepts_number_that_appears_in_the_cited_metric():
    fact = _achievement(
        1,
        statement="Reduced latency from 320ms to 90ms.",
        metric_value="reduced latency from 320ms to 90ms",
        metric_verified=True,
    )
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="Reduced latency from 320ms to 90ms.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) is None


def test_v3_rejects_number_from_an_unverified_metric():
    fact = _achievement(1, metric_value="improved throughput by 40%", metric_verified=False)
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(text="Improved throughput by 40%.", supporting_fact_ids=[fact_id_of(fact)])

    assert verify_bullet(bullet, ctx) == "UNVERIFIED_METRIC"


def test_v4_rejects_technology_not_in_cited_tags_or_skills():
    fact = _achievement(1, technology_tags=["docker"])
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="Deployed services using Kubernetes.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) == "UNKNOWN_TECHNOLOGY"


def test_v4_accepts_technology_present_in_cited_tags():
    fact = _achievement(
        1,
        statement="Deployed services using Kubernetes and Docker.",
        technology_tags=["kubernetes", "docker"],
    )
    ctx = GroundingContext.build(_profile_with(achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="Deployed services using Kubernetes and Docker.",
        supporting_fact_ids=[fact_id_of(fact)],
    )

    assert verify_bullet(bullet, ctx) is None


def test_v4_accepts_technology_present_in_profile_skill_list():
    skill = CareerSkill(id=1, name="aws")
    fact = _achievement(1, statement="Operated infrastructure on AWS.")
    ctx = GroundingContext.build(_profile_with(achievements=[fact], skills=[skill]), [fact])
    bullet = DraftBullet(
        text="Operated infrastructure on AWS.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) is None


def test_v5_rejects_a_different_known_employer():
    real_exp = _experience(1, company="Acme Corp")
    other_exp = _experience(2, company="Globex Inc")
    fact = _achievement(1, experience=real_exp)
    ctx = GroundingContext.build(
        _profile_with(experiences=[real_exp, other_exp], achievements=[fact]), [fact]
    )
    bullet = DraftBullet(
        text="Led the platform team at Globex Inc.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) == "UNKNOWN_EMPLOYER"


def test_v5_accepts_the_cited_experiences_own_company():
    exp = _experience(1, company="Acme Corp")
    fact = _achievement(1, statement="Led the platform team at Acme Corp.", experience=exp)
    ctx = GroundingContext.build(_profile_with(experiences=[exp], achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="Led the platform team at Acme Corp.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) is None


def test_v6_rejects_duration_beyond_the_cited_experiences_span():
    exp = _experience(1, years_ago=2, is_current=True)
    fact = _achievement(1, experience=exp)
    ctx = GroundingContext.build(_profile_with(experiences=[exp], achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="8 years of experience leading this team.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) == "DATE_INCONSISTENT"


def test_v6_accepts_duration_within_the_cited_experiences_span():
    exp = _experience(1, years_ago=3, is_current=True)
    fact = _achievement(1, statement="3 years of experience leading this team.", experience=exp)
    ctx = GroundingContext.build(_profile_with(experiences=[exp], achievements=[fact]), [fact])
    bullet = DraftBullet(
        text="3 years of experience leading this team.", supporting_fact_ids=[fact_id_of(fact)]
    )

    assert verify_bullet(bullet, ctx) is None


def test_verify_draft_drops_only_the_failing_bullet_and_reports_it():
    exp = _experience(1)
    good_fact = _achievement(
        1, statement="Built things in Python.", experience=exp, skill_tags=["python"]
    )
    profile = _profile_with(experiences=[exp], achievements=[good_fact])
    ctx = GroundingContext.build(profile, [good_fact])

    draft = CVDraft(
        summary=DraftBullet(text=good_fact.statement, supporting_fact_ids=[fact_id_of(good_fact)]),
        experience=[
            DraftExperienceBlock(
                experience_id=1,
                bullets=[
                    DraftBullet(
                        text="Built things in Python.", supporting_fact_ids=[fact_id_of(good_fact)]
                    ),
                    DraftBullet(text="Invented claim.", supporting_fact_ids=[]),
                ],
            )
        ],
    )

    cleaned, report = verify_draft(draft, ctx)

    assert report.claims_checked == 3  # summary + 2 bullets
    assert report.claims_rejected == 1
    assert report.rejections[0].reason == "NO_SUPPORTING_FACT"
    assert len(cleaned.experience[0].bullets) == 1
    assert cleaned.experience[0].bullets[0].text == "Built things in Python."


def test_verify_draft_all_rejected_yields_empty_content():
    ctx = GroundingContext.build(_profile_with(), [])
    draft = CVDraft(summary=DraftBullet(text="Fabricated summary.", supporting_fact_ids=[]))

    cleaned, report = verify_draft(draft, ctx)

    assert cleaned.summary.text == ""
    assert report.claims_rejected == 1
