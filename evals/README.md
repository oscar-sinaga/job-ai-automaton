# evals/ — LLM quality evaluation

Fixtures live here (data only); the runnable harness lives in `apps/api/scripts/eval_cv_grounding.py`, since it needs to import `oscar_api` directly (ADR-024) — a separate `evals` Python package at repo root would need its own environment wired to the API's, for no real benefit at this scale.

Design: [../docs/07_CV_GROUNDING_AND_EVALS.md](../docs/07_CV_GROUNDING_AND_EVALS.md) §6–§8, [../docs/12_TEST_STRATEGY.md](../docs/12_TEST_STRATEGY.md) §5.

Evals are **not** part of CI: they cost money and are non-deterministic (and require a real `OPENAI_API_KEY`, which no CI run or test in this repo ever provides). They run on demand and gate any prompt or model change.

```bash
cd apps/api
uv run python scripts/eval_cv_grounding.py --case ../../evals/cv_grounding/cases/001_mlops_engineer
uv run python scripts/eval_cv_grounding.py --case ../../evals/cv_grounding/adversarial/a01_metric_inflation
```

## Current layout

```text
evals/
  cv_grounding/
    profiles/oscar_sanitised.json         # sanitised fixture profile (2 experiences, 1 project, 4 achievements)
    cases/001_mlops_engineer/{jd.txt,expected.json}
    adversarial/
      a01_metric_inflation/{jd.txt,notes.md}   # JD baits an unverified % improvement
      a02_adjacent_tech/{jd.txt,notes.md}      # JD wants Kubernetes; profile has only Docker
      # a03_seniority_stretch, a04_invented_leadership, a05_phantom_certification:
      # sketched in docs/07 §6, not yet built -- add as real near-misses surface
  results/                                # eval run output, not yet wired up (harness currently prints to stdout)
```

## Gates

| Suite | Metric | Gate |
|---|---|---|
| `cv_grounding` | fabrication rate | **must be 0** |
| `cv_grounding` | verifier recall on adversarial cases | **must be 100%** |
| `cv_grounding` | verifier precision, fact recall | tracked, not gating |
| `job_extraction` | field accuracy | not yet built (parser is P1, non-blocking by design) |

The adversarial cases are the ones that actually protect the product's core promise. Every real-world near-miss found during Milestone 6 becomes a new adversarial case — the suite is meant to grow from experience, not to be written once.

## Status

Built this session, **not yet run**: this environment has no `OPENAI_API_KEY`, so the harness has never actually executed against a real model. The grounding *verifier* itself is thoroughly unit-tested (`apps/api/tests/test_grounding.py`, no API key needed); what's unverified is the *generator's* real-world behavior against these specific adversarial baits. Run both cases above before trusting CV generation with real applications.
