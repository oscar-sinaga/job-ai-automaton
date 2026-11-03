# evals/ — LLM quality evaluation

Fixtures live here (data only); the runnable harness lives in `apps/api/scripts/eval_cv_grounding.py`, since it needs to import `oscar_api` directly (ADR-024) — a separate `evals` Python package at repo root would need its own environment wired to the API's, for no real benefit at this scale.

Design: [../docs/07_CV_GROUNDING_AND_EVALS.md](../docs/07_CV_GROUNDING_AND_EVALS.md) §6–§8, [../docs/12_TEST_STRATEGY.md](../docs/12_TEST_STRATEGY.md) §5.

Evals are **not** part of CI: they cost money and are non-deterministic (and require a real `OPENAI_API_KEY`, which no CI run or test in this repo ever provides). They run on demand and gate any prompt or model change.

```bash
cd apps/api
uv run python scripts/eval_cv_grounding.py --case ../../evals/cv_grounding/cases/001_mlops_engineer
uv run python scripts/eval_cv_grounding.py --case ../../evals/cv_grounding/adversarial/a01_metric_inflation
uv run python scripts/eval_cv_grounding.py --suite --env-file ../../.env.pilot \
  --json-output ../../var/logs/live-eval.json
```

## Current layout

```text
evals/
  cv_grounding/
    profiles/oscar_sanitised.json         # sanitised fixture profile (2 experiences, 1 project, 4 achievements)
    cases/001_mlops_engineer/{jd.txt,expected.json}
    adversarial/
      a01_metric_inflation/{jd.txt,notes.md,expected.json}
      a02_adjacent_tech/{jd.txt,notes.md,expected.json}
      a03_jd_injection/{jd.txt,expected.json}
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

The four-case harness now checks expected retrieval, nonempty supported content,
forbidden candidate claims and required missing-skill disclosures. Skills are
checked as claims; honest missing requirements are evaluated separately. Empty
output cannot pass by omission. A failed case exits nonzero, and machine-readable
results include the actual model, prompt version, latency, usage and rejections.

The in-memory fixture preserves experience/project IDs exactly as the database
does. Offline regressions verify this and the evaluator's failure conditions.

On 2026-11-03 the owner explicitly approved sending these public synthetic
fixtures to OpenAI and requested a cheap model. All **four real-API cases passed**
using `gpt-6-luna`, reasoning `none`, a 4,096-output-token cap and no SDK retries.
[Recorded evidence](cv_grounding/results/2026-11-03_gpt-6-luna.json) contains the
actual drafts, checks, source hashes, model, latency and token usage: 4,289 input
and 561 output tokens, 24 claims/skills checked, zero rejections in this sample.
The positive case retrieved all three expected facts. Latency was 8.7–9.5 seconds
per request; this is a four-case sample, not a p95 or a reliability guarantee.

At the official standard token prices checked that day, the token-price estimate
is $0.0007094; assuming all input were charged as cache writes gives $0.000816625.
These estimates are not an account invoice. The fixture suite contains no real
user career profile. `store=false` disables
response retrieval storage, not the account's separate retention policy; see
[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).
