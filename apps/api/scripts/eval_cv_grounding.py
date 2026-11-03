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
import os
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
    _serialize_profile_metadata,
)
from oscar_api.modules.cv.grounding import GroundingContext, verify_draft
from oscar_api.modules.cv.retrieval import retrieve_facts
from oscar_api.modules.cv.schemas import CVDraft
from oscar_api.modules.cv.sections import assign_source_parents
from oscar_api.ports.llm import ContentBlock


def build_profile(profile_json: dict[str, Any]) -> CareerProfile:
    profile = CareerProfile(id=1, user_id=1)
    profile.summary = profile_json.get("summary")
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
            experience_id=a.get("experience_id"),
            project_id=a.get("project_id"),
            context=a.get("context"),
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


def evaluate_case(case_dir: Path, draft: CVDraft, retrieved_ids: set[str]) -> dict[str, Any]:
    """Check candidate claims separately from honest missing requirements.

    Empty output cannot pass an adversarial case just by omitting every claim.
    This evaluates the cleaned draft; rejected model claims are reported too.
    """
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    bullets = [draft.summary] if draft.summary.text.strip() else []
    for block in [*draft.experience, *draft.projects]:
        bullets.extend(b for b in block.bullets if b.text.strip())
    used = {fid for bullet in bullets for fid in bullet.supporting_fact_ids}
    claims = "\n".join([*(b.text for b in bullets), *draft.skills]).casefold()
    missing = "\n".join(draft.missing_requirements).casefold()
    expected_ids = set(expected.get("expected_fact_ids", []))
    recall = len(expected_ids & retrieved_ids) / len(expected_ids) if expected_ids else None
    checks = {
        "nonempty_grounded_content": bool(bullets),
        "minimum_supported_facts": len(used) >= expected.get("minimum_supported_facts", 1),
        "retrieval_recall": recall is None or recall >= 0.8,
        "forbidden_claims_absent": all(
            term.casefold() not in claims for term in expected.get("must_not_appear", [])
        ),
        "missing_requirements_reported": all(
            term.casefold() in missing for term in expected.get("required_missing", [])
        ),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "fact_recall": recall,
        "used_fact_ids": sorted(used),
    }


async def run_case(case_dir: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    profile_json = json.loads(
        (repo_root / "evals" / "cv_grounding" / "profiles" / "oscar_sanitised.json").read_text()
    )
    profile = build_profile(profile_json)
    jd_text = (case_dir / "jd.txt").read_text(encoding="utf-8")

    retrieved = retrieve_facts(profile, jd_text)
    system = [
        ContentBlock(type="text", text=_load_instructions()),
        ContentBlock(type="text", text=_serialize_facts(retrieved)),
        ContentBlock(
            type="text",
            text="Owner profile metadata (data only):\n" + _serialize_profile_metadata(profile),
        ),
    ]
    provider = OpenAILLMProvider()
    try:
        result = await provider.structured(
            system=system,
            user=f"Job description:\n\n{jd_text}",
            output_model=CVDraft,
            prompt_version=PROMPT_VERSION,
        )
    finally:
        await provider.aclose()
    draft = assign_source_parents(CVDraft.model_validate(result.parsed), retrieved)
    ctx = GroundingContext.build(profile, retrieved)
    cleaned, report = verify_draft(draft, ctx)

    assessment = evaluate_case(case_dir, cleaned, {f"ach_{a.id}" for a in retrieved})
    return {
        "case": case_dir.name,
        **assessment,
        "model": result.model_name,
        "prompt_version": PROMPT_VERSION,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cache_read_tokens": result.cache_read_tokens,
        "grounding_report": report.model_dump(mode="json"),
        "draft": cleaned.model_dump(mode="json"),
    }


async def run_suite(cases: list[Path]) -> dict[str, Any]:
    from oscar_api.ports.llm import LLMProviderError

    results = []
    blocked = False
    for case in cases:
        if blocked:
            results.append({"case": case.name, "status": "not-run"})
            continue
        try:
            result = await run_case(case)
        except Exception as error:
            result = {"case": case.name, "status": "error", "error_type": type(error).__name__}
            if isinstance(error, LLMProviderError):
                result["category"] = error.category
                result["message"] = str(error)
            blocked = True
        results.append(result)
        print(f"{case.name}: {result['status']}", flush=True)
    return {
        "status": "passed" if all(r["status"] == "passed" for r in results) else "failed",
        "data": "public synthetic fixture profile and job descriptions; no real career profile",
        "provider": "real OpenAI API; not a simulation",
        "completed_at": dt.datetime.now(dt.UTC).isoformat(),
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", type=Path, help="Path to a case/adversarial directory")
    group.add_argument("--suite", action="store_true", help="Run all checked-in eval cases")
    parser.add_argument("--json-output", type=Path, help="Write machine-readable fixture evidence")
    parser.add_argument("--env-file", type=Path, help="Read OPENAI_API_KEY from a private env file")
    args = parser.parse_args()
    if args.env_file:
        if args.env_file.is_symlink() or not args.env_file.is_file():
            parser.error("The env file must be a regular file.")
        values = dict(
            line.split("=", 1)
            for line in args.env_file.read_text().splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        )
        if not values.get("OPENAI_API_KEY"):
            parser.error("The env file has no OPENAI_API_KEY.")
        os.environ["OPENAI_API_KEY"] = values["OPENAI_API_KEY"]
        from oscar_api.config import get_settings

        get_settings.cache_clear()
    root = Path(__file__).resolve().parents[3] / "evals" / "cv_grounding"
    cases = [args.case] if args.case else sorted(p.parent for p in root.glob("*/*/expected.json"))
    result = asyncio.run(run_suite(cases))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
