"""The deterministic grounding verifier (docs/07_CV_GROUNDING_AND_EVALS.md §3).

This is the file G3 ([01_PRD] §5: zero fabricated claims) depends on. Every
rule is a pure function over `(bullet, context)`, checked against the
*retrieved* fact set -- a fact ID that exists in the database but was never
given to the model is treated as fabrication, not a lucky guess, because
accepting it would defeat the entire mechanism (docs/07 §3, rule V1 note).

Scope simplification vs. the documented pipeline (recorded as ADR-023): V1 does
ONE verification pass and drops failing bullets immediately -- it does not
attempt an automated LLM repair-and-retry round before dropping. This keeps
the safety property (fail closed, never keep an unsupported claim) while
cutting an LLM round-trip; it only means more bullets get dropped instead of
silently fixed, which is strictly safer, not less safe.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass

from oscar_api.modules.career.models import CareerAchievement, CareerProfile
from oscar_api.modules.cv.schemas import (
    CVDraft,
    DraftBullet,
    DraftExperienceBlock,
    DraftProjectBlock,
    GroundingRejection,
    GroundingReport,
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?%?")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\+?\s*years?", re.IGNORECASE)

# Seed vocabulary for V4 (docs/07 §3: "seeded from the profile's own skills
# plus a static list"). Deliberately small and biased toward over-flagging --
# a false rejection costs one regenerated bullet; a false acceptance costs the
# product's core promise.
KNOWN_TECHNOLOGY_TERMS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "sql", "postgresql", "mysql", "mongodb", "redis",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "fastapi", "django", "flask", "react", "svelte", "vue", "node.js",
    "pytorch", "tensorflow", "scikit-learn", "spark", "airflow", "kafka",
    "mlflow", "sagemaker", "hugging face", "langchain",
}  # fmt: skip


def fact_id_of(achievement: CareerAchievement) -> str:
    return f"ach_{achievement.id}"


@dataclass
class GroundingContext:
    retrieved_facts: dict[str, CareerAchievement]  # fact_id -> achievement
    profile_skill_names: set[str]
    known_company_names: set[str]  # every company name in the profile

    @classmethod
    def build(cls, profile: CareerProfile, retrieved: list[CareerAchievement]) -> GroundingContext:
        return cls(
            retrieved_facts={fact_id_of(a): a for a in retrieved},
            profile_skill_names={s.name.lower() for s in profile.skills},
            known_company_names={e.company.lower() for e in profile.experiences},
        )


def _numbers_in(text: str) -> set[str]:
    """Numbers that could be a fabricated *metric* -- excludes duration
    numbers like "8 years", which V6 checks separately against the cited
    experience's actual span. Without this exclusion, V2 would reject every
    tenure claim before V6 ever ran (it matches "8" as an ungrounded number
    the same way it would match "70%")."""
    duration_numbers = set(_YEARS_RE.findall(text))
    return set(_NUMBER_RE.findall(text)) - duration_numbers


def _cited_facts(bullet: DraftBullet, ctx: GroundingContext) -> list[CareerAchievement]:
    return [
        ctx.retrieved_facts[fid] for fid in bullet.supporting_fact_ids if fid in ctx.retrieved_facts
    ]


# ── V1: every cited fact ID must be in the retrieved set ────────────────────


def check_fact_ids(bullet: DraftBullet, ctx: GroundingContext) -> str | None:
    if not bullet.supporting_fact_ids:
        return "NO_SUPPORTING_FACT"
    for fid in bullet.supporting_fact_ids:
        if fid not in ctx.retrieved_facts:
            return "FACT_NOT_RETRIEVED"
    return None


# ── V2: every number in the bullet must appear in a cited fact's metric ─────


def check_metric_match(bullet: DraftBullet, cited: list[CareerAchievement]) -> str | None:
    bullet_numbers = _numbers_in(bullet.text)
    if not bullet_numbers:
        return None
    allowed: set[str] = set()
    for fact in cited:
        if fact.metric_value:
            allowed |= _numbers_in(fact.metric_value)
    if not bullet_numbers.issubset(allowed):
        return "METRIC_MISMATCH"
    return None


# ── V3: a cited metric must be verified before its number is usable ────────


def check_metric_verified(bullet: DraftBullet, cited: list[CareerAchievement]) -> str | None:
    bullet_numbers = _numbers_in(bullet.text)
    if not bullet_numbers:
        return None
    for fact in cited:
        cites_this_number = fact.metric_value and (_numbers_in(fact.metric_value) & bullet_numbers)
        if cites_this_number and not fact.metric_verified:
            return "UNVERIFIED_METRIC"
    return None


# ── V4: technology/skill terms must come from cited tags or the skill list ─


def check_known_technology(
    bullet: DraftBullet, cited: list[CareerAchievement], ctx: GroundingContext
) -> str | None:
    allowed: set[str] = set(ctx.profile_skill_names)
    for fact in cited:
        allowed |= {t.lower() for t in fact.skill_tags}
        allowed |= {t.lower() for t in fact.technology_tags}

    text_lower = bullet.text.lower()
    for term in KNOWN_TECHNOLOGY_TERMS:
        if term in text_lower and term not in allowed:
            return "UNKNOWN_TECHNOLOGY"
    return None


# ── V5: no employer name outside the cited experience(s) ───────────────────


def check_known_employer(
    bullet: DraftBullet, cited: list[CareerAchievement], ctx: GroundingContext
) -> str | None:
    cited_companies = {
        fact.experience.company.lower() for fact in cited if fact.experience is not None
    }
    text_lower = bullet.text.lower()
    for company in ctx.known_company_names:
        if company in text_lower and company not in cited_companies:
            return "UNKNOWN_EMPLOYER"
    return None


# ── V6: a claimed duration must not exceed the cited experience's span ──────


def check_date_consistency(bullet: DraftBullet, cited: list[CareerAchievement]) -> str | None:
    claimed_years = [float(m) for m in _YEARS_RE.findall(bullet.text)]
    if not claimed_years:
        return None

    max_claimed = max(claimed_years)
    for fact in cited:
        exp = fact.experience
        if exp is None:
            continue
        end = exp.end_date or dt.date.today()
        actual_years = max((end - exp.start_date).days / 365.25, 0.0)
        # A little slack for "about N years" rounding; not for a multi-year gap.
        if max_claimed > actual_years + 1.0:
            return "DATE_INCONSISTENT"
    return None


_Rule = Callable[[DraftBullet, list[CareerAchievement], GroundingContext], "str | None"]

_RULES: list[_Rule] = [
    lambda b, cited, ctx: check_fact_ids(b, ctx),
    lambda b, cited, ctx: check_metric_match(b, cited),
    lambda b, cited, ctx: check_metric_verified(b, cited),
    lambda b, cited, ctx: check_known_technology(b, cited, ctx),
    lambda b, cited, ctx: check_known_employer(b, cited, ctx),
    lambda b, cited, ctx: check_date_consistency(b, cited),
]


def verify_bullet(bullet: DraftBullet, ctx: GroundingContext) -> str | None:
    """Returns None if the bullet passes every rule, else the first failing
    rule's reason code."""
    cited = _cited_facts(bullet, ctx)
    for rule in _RULES:
        if reason := rule(bullet, cited, ctx):
            return reason
    return None


def verify_draft(draft: CVDraft, ctx: GroundingContext) -> tuple[CVDraft, GroundingReport]:
    """Verifies every bullet in the draft, dropping (not repairing -- ADR-023)
    any that fail. Returns the cleaned draft plus a report of what happened."""
    checked = 0
    rejections: list[GroundingRejection] = []

    def _keep(bullet: DraftBullet) -> bool:
        nonlocal checked
        checked += 1
        reason = verify_bullet(bullet, ctx)
        if reason is not None:
            rejections.append(GroundingRejection(text=bullet.text, reason=reason))
            return False
        return True

    summary = (
        draft.summary if _keep(draft.summary) else DraftBullet(text="", supporting_fact_ids=[])
    )

    cleaned_experience: list[DraftExperienceBlock] = []
    for exp_block in draft.experience:
        kept_bullets = [b for b in exp_block.bullets if _keep(b)]
        if kept_bullets:
            cleaned_experience.append(exp_block.model_copy(update={"bullets": kept_bullets}))

    cleaned_projects: list[DraftProjectBlock] = []
    for proj_block in draft.projects:
        kept_bullets = [b for b in proj_block.bullets if _keep(b)]
        if kept_bullets:
            cleaned_projects.append(proj_block.model_copy(update={"bullets": kept_bullets}))

    cleaned = draft.model_copy(
        update={"summary": summary, "experience": cleaned_experience, "projects": cleaned_projects}
    )
    report = GroundingReport(
        claims_checked=checked, claims_rejected=len(rejections), rejections=rejections
    )
    return cleaned, report
