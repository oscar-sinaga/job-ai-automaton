"""Deterministic fact retrieval (docs/07_CV_GROUNDING_AND_EVALS.md §3 step 2).

No embeddings, no vector store (ADR-009): every retrieval decision is a
transparent score over tags the user themself entered. Misses semantic
near-matches (a `MLflow` tag won't score against "experiment tracking" in a
JD) -- accepted for V1, revisit only if eval `fact_recall` proves it binding
(OPEN-4).
"""

from __future__ import annotations

from oscar_api.modules.career.models import CareerAchievement, CareerProfile

TOP_N_OVERALL = 30
# Requirement extraction has no job_parsed_data to read yet (parser is a
# separate, later concern) -- keyword-match the raw JD against the profile's
# own vocabulary instead, per docs/07 §3 step 1 "else keyword extraction".
_SKILL_WEIGHT = 3.0
_TECH_WEIGHT = 3.0
_DOMAIN_WEIGHT = 1.5
_VERIFIED_BONUS = 1.0
_CURRENT_ROLE_BONUS = 1.0
_LINKED_ROLE_BONUS = 0.5


def _lower_set(values: list[str]) -> set[str]:
    return {v.lower() for v in values}


def build_vocabulary(profile: CareerProfile) -> set[str]:
    vocab: set[str] = {s.name for s in profile.skills}
    for achievement in profile.achievements:
        vocab |= set(achievement.skill_tags) | set(achievement.domain_tags)
        vocab |= set(achievement.technology_tags)
    return {v.lower() for v in vocab if v}


def match_requirements(raw_jd_text: str, vocabulary: set[str]) -> set[str]:
    """Which of the profile's own terms literally appear in the JD text."""
    text_lower = raw_jd_text.lower()
    return {term for term in vocabulary if term in text_lower}


def _recency_bonus(achievement: CareerAchievement) -> float:
    if achievement.experience is not None:
        return _CURRENT_ROLE_BONUS if achievement.experience.is_current else _LINKED_ROLE_BONUS
    if achievement.project is not None:
        return _LINKED_ROLE_BONUS
    return 0.0


def score_achievement(achievement: CareerAchievement, matched_terms: set[str]) -> float:
    score = _SKILL_WEIGHT * len(_lower_set(achievement.skill_tags) & matched_terms)
    score += _TECH_WEIGHT * len(_lower_set(achievement.technology_tags) & matched_terms)
    score += _DOMAIN_WEIGHT * len(_lower_set(achievement.domain_tags) & matched_terms)
    if achievement.verification_status == "verified":
        score += _VERIFIED_BONUS
    score += _recency_bonus(achievement)
    return score


def retrieve_facts(
    profile: CareerProfile, raw_jd_text: str, top_n: int = TOP_N_OVERALL
) -> list[CareerAchievement]:
    """Top-N active achievements, ranked by JD relevance.

    Falls back to recency/verification ordering (not an empty set) when the
    JD shares no vocabulary with the profile at all -- CV generation should
    still have facts to work with, just less targeted ones.
    """
    active = [a for a in profile.achievements if a.deleted_at is None]
    matched_terms = match_requirements(raw_jd_text, build_vocabulary(profile))
    ranked = sorted(active, key=lambda a: score_achievement(a, matched_terms), reverse=True)
    return ranked[:top_n]
