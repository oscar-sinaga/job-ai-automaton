# agents/ — LLM agent prompts

Design: [../docs/06_AI_LLM_DESIGN.md](../docs/06_AI_LLM_DESIGN.md), [../docs/07_CV_GROUNDING_AND_EVALS.md](../docs/07_CV_GROUNDING_AND_EVALS.md).

| Agent | Status | Purpose |
|---|---|---|
| `cv_generator/` | **Built (M3)** | Draft tailored CV sections, each bullet citing `supporting_fact_ids` |
| `job_parser/` | Not built (P1) | Best-effort JD → structured fields with confidence. Never blocks anything |
| `fit_scorer/` | Not built (P1, post-V1) | Explainable component scores, not an opaque number |
| `question_assistant/` | Not built (P1, post-V1) | Draft answers to application questions, always human-reviewed |

## Actual layout

```text
agents/cv_generator/prompts/v1.md      # the frozen instructions text -- versioned;
                                        # never edited in place once used
```

Only the **prompt text** lives here. The orchestration (retrieval → LLM call → grounding verification → persistence) is implemented in `apps/api/src/oscar_api/modules/cv/generator.py`, `retrieval.py`, and `grounding.py` — a modular monolith is one deployable (ADR-003), so there's no separate `agents/cv_generator/*.py` process or package; this directory is a signpost for the prompt only, matching how `domain/README.md` and `workers/README.md` are signposts for other master-spec-suggested top-level directories.

Prompt version and model name are recorded per run in `cv_generation_runs`, so any output can be traced to an exact (prompt, model) pair. Adopting a new version requires a passing eval run first ([../evals/README.md](../evals/README.md)).

Agents call the LLM only through the `LLMProvider` port — nothing here imports the `openai` SDK directly (ADR-025; only `apps/api/src/oscar_api/adapters/openai_provider.py` does).
