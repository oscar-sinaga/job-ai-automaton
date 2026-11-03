"""The live-eval gate must reject vacuous/incorrect outputs before model adoption."""

import importlib.util
import json
from pathlib import Path

from oscar_api.modules.cv.generator import _serialize_facts
from oscar_api.modules.cv.schemas import CVDraft, DraftBullet

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "eval_cv_grounding", ROOT / "apps/api/scripts/eval_cv_grounding.py"
)
assert spec and spec.loader
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


def test_in_memory_profile_preserves_prompt_parent_ids():
    fixture = json.loads((ROOT / "evals/cv_grounding/profiles/oscar_sanitised.json").read_text())
    profile = harness.build_profile(fixture)
    facts = json.loads(_serialize_facts(profile.achievements))
    assert [f["experience_id"] for f in facts] == [1, 1, 2, None]
    assert [f["project_id"] for f in facts] == [None, None, None, 1]


def test_empty_draft_cannot_pass_an_adversarial_eval():
    result = harness.evaluate_case(
        ROOT / "evals/cv_grounding/adversarial/a01_metric_inflation",
        CVDraft(summary=DraftBullet(text="")),
        {"ach_1"},
    )
    assert result["status"] == "failed"
    assert not result["checks"]["nonempty_grounded_content"]


def test_missing_requirement_is_not_counted_as_candidate_claim():
    case = ROOT / "evals/cv_grounding/adversarial/a02_adjacent_tech"
    draft = CVDraft(
        summary=DraftBullet(text="Used Docker", supporting_fact_ids=["ach_2"]),
        skills=["Docker"],
        missing_requirements=["Kubernetes, Helm, ArgoCD"],
    )
    assert harness.evaluate_case(case, draft, {"ach_2"})["status"] == "passed"
    draft.skills.append("Kubernetes")
    assert harness.evaluate_case(case, draft, {"ach_2"})["status"] == "failed"


def test_positive_eval_requires_expected_retrieval_and_multiple_facts():
    draft = CVDraft(summary=DraftBullet(text="One fact", supporting_fact_ids=["ach_1"]))
    result = harness.evaluate_case(
        ROOT / "evals/cv_grounding/cases/001_mlops_engineer", draft, {"ach_1"}
    )
    assert result["status"] == "failed"
    assert not result["checks"]["retrieval_recall"]
    assert not result["checks"]["minimum_supported_facts"]
