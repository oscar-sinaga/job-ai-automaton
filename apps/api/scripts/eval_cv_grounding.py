"""CV grounding eval harness (docs/07_CV_GROUNDING_AND_EVALS.md §6-8).

Runs the real generation pipeline (retrieval -> real OpenAI call -> the
same `grounding.verify_draft` used in production) against a fixture profile
and a fixture JD, without touching the database at all -- the profile is
built as in-memory ORM objects, the same technique `tests/test_grounding.py`
uses for unit tests.

Requires OPENAI_API_KEY. This is deliberately NOT run in CI (docs/12 §5):
it costs money and is non-deterministic. Run manually before adopting a new
prompt or model version.

Usage:
    cd apps/api
    uv run python scripts/eval_cv_grounding.py \
        --case ../../evals/cv_grounding/cases/001_mlops_engineer
    uv run python scripts/eval_cv_grounding.py \
        --case ../../evals/cv_grounding/adversarial/a01_metric_inflation
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oscar_api.adapters.openai_provider import OpenAILLMProvider
from oscar_api.modules.career.models import (
    CareerAchievement,
    CareerExperience,
    CareerProfile,
    CareerProject,
    CareerSkill,
)
from oscar_api.modules.cv.generator import (
    PROMPT_VERSION,
    _load_instructions,
    _serialize_facts,
)
from oscar_api.modules.cv.grounding import GroundingContext, verify_draft
from oscar_api.modules.cv.retrieval import retrieve_facts
from oscar_api.modules.cv.schemas import CVDraft
from oscar_api.ports.llm import ContentBlock


def build_profile(profile_json: dict[str, Any]) -> CareerProfile:
    profile = CareerProfile(id=1, user_id=1)
    experiences = {
        e["id"]: CareerExperience(
            id=e["id"],
            company=e["company"],
            title=e["title"],
            start_date=dt.date.fromisoformat(e["start_date"]),
            end_date=dt.date.fromisoformat(e["end_date"]) if e.get("end_date") else None,
            is_current=e.get("is_current", False),
        )
        for e in profile_json.get("experiences", [])
    }
    projects = {
        p["id"]: CareerProject(id=p["id"], name=p["name"]) for p in profile_json.get("projects", [])
    }
    skills = [
        CareerSkill(id=i, name=s["name"]) for i, s in enumerate(profile_json.get("skills", []), 1)
    ]

    achievements = []
    for a in profile_json.get("achievements", []):
        achievement = CareerAchievement(
            id=a["id"],
            statement=a["statement"],
            metric_value=a.get("metric_value"),
            metric_verified=a.get("metric_verified", False),
            skill_tags=a.get("skill_tags", []),
            technology_tags=a.get("technology_tags", []),
            domain_tags=a.get("domain_tags", []),
        )
        achievement.experience = experiences.get(a.get("experience_id"))
        achievement.project = projects.get(a.get("project_id"))
        achievements.append(achievement)

    profile.experiences = list(experiences.values())
    profile.projects = list(projects.values())
    profile.skills = skills
    profile.achievements = achievements
    return profile


async def run_case(case_dir: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    profile_json = json.loads(
        (repo_root / "evals" / "cv_grounding" / "profiles" / "oscar_sanitised.json").read_text()
    )
    profile = build_profile(profile_json)
    jd_text = (case_dir / "jd.txt").read_text(encoding="utf-8")

    retrieved = retrieve_facts(profile, jd_text)
    print(f"Retrieved {len(retrieved)} facts: {[f'ach_{a.id}' for a in retrieved]}")

    system = [
        ContentBlock(type="text", text=_load_instructions()),
        ContentBlock(type="text", text=_serialize_facts(retrieved)),
    ]
    provider = OpenAILLMProvider()
    result = await provider.structured(
        system=system,
        user=f"Job description:\n\n{jd_text}",
        output_model=CVDraft,
        prompt_version=PROMPT_VERSION,
    )
    draft = CVDraft.model_validate(result.parsed)
    ctx = GroundingContext.build(profile, retrieved)
    cleaned, report = verify_draft(draft, ctx)

    print(
        f"\nModel: {result.model_name}  latency: {result.latency_ms}ms  "
        f"tokens in/out: {result.input_tokens}/{result.output_tokens}"
    )
    print(f"Claims checked: {report.claims_checked}  rejected: {report.claims_rejected}")
    for rejection in report.rejections:
        print(f"  REJECTED [{rejection.reason}]: {rejection.text}")
    print("\nFinal (grounded) draft:")
    print(cleaned.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="Path to a case/adversarial directory")
    args = parser.parse_args()
    asyncio.run(run_case(Path(args.case)))


if __name__ == "__main__":
    main()
