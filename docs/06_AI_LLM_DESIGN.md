# 06 — AI / LLM Design

Implemented in Milestone 3. This is the binding design for `agents/job_parser`, `agents/cv_generator`, `agents/fit_scorer`, `agents/question_assistant`.

API facts below (model IDs, pricing, parameter shapes) were verified against current OpenAI documentation and the installed SDK's type stubs on 2026-08-28 (ADR-025). Re-verify before changing providers or models again — this surface has changed materially over time.

---

## 1. Provider Abstraction

A single interface, independent of any specific vendor SDK:

```python
class LLMProvider(Protocol):
    async def structured(
        self, *, system: list[ContentBlock], user: str, output_model: type[T],
        prompt_version: str, effort: str = "high", timeout_s: float = 90.0,
    ) -> LLMResult: ...
```

Nothing in `modules/` imports `openai` directly. The single implementation lives in `adapters/openai_provider.py`; tests inject a `FakeLLMProvider` that returns fixture payloads, which is what lets the entire grounding pipeline be tested without network access ([12_TEST_STRATEGY](12_TEST_STRATEGY.md)).

**Default implementation: OpenAI**, via the official `openai` Python SDK's async client (`AsyncOpenAI`), using the **Responses API**'s `.parse()` helper (ADR-025 — switched from an earlier Anthropic-based default; nothing outside the one adapter file needed to change, which is the entire point of the port). Swappable later to another vendor or a local model without touching any caller.

## 2. Model Selection

| Use | Model | Rationale |
|---|---|---|
| CV generation (default) | `gpt-4.1` | Strong instruction-following and structured-output reliability at a moderate cost; grounding fidelity (G3) is the product's hard constraint, so quality is prioritised over the cheaper mini/nano tiers |
| JD parsing | `gpt-4.1` | Same default; parsing errors are cheap to correct, so this is the first place to trade down (e.g. to `gpt-4.1-mini`) if cost or latency matters |
| Fit score / question assistant (P1) | `gpt-4.1` | Not implemented in V1 |

Model choice is a config value (`OSCAR_LLM_MODEL`, `OSCAR_LLM_PARSER_MODEL`), not a constant. Documented alternatives if the owner chooses to trade cost for quality:

| Model | Input $/MTok | Cached input $/MTok | Output $/MTok |
|---|---|---|---|
| `gpt-4.1` (default) | $2.00 | $0.50 | $8.00 |
| `gpt-4.1-mini` | $0.40 | — | $1.60 |
| `gpt-4.1-nano` | $0.10 | — | — |

Downgrading is the owner's decision, not an automatic optimisation — for the parser it is low-risk, for CV generation it directly touches G3 and must be re-validated against the eval set ([07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md)) before adoption.

## 3. Structured Output

Every call is schema-constrained via the Responses API's `.parse()` helper, passing a Pydantic model directly as `text_format`:

```python
response = await client.responses.parse(
    model=settings.llm_model,
    input=[
        {"role": "system", "content": frozen_instructions},
        {"role": "system", "content": serialised_career_facts},
        {"role": "user", "content": jd_text},
    ],
    text_format=CVDraft,   # a Pydantic model; SDK enforces the JSON schema
)
draft: CVDraft = response.output_parsed
```

Free-text parsing is never used, because the grounding verifier depends on receiving `supporting_fact_ids` as data, not prose to be re-parsed. `response.output_parsed` is `None` if the model's output didn't validate against the schema — the adapter treats that as a hard failure (`RuntimeError`), never as an empty success.

`gpt-4.1` is **not a reasoning model**: the port's `effort` parameter (used by earlier reasoning-model-oriented adapters) has nothing to map to on this model and is accepted-but-ignored by `OpenAILLMProvider`, documented in the adapter itself rather than silently repurposed. A future adapter for a reasoning-tier OpenAI model (e.g. an `o`-series or `gpt-5`-series model) would map `effort` onto that model's `reasoning={"effort": ...}` parameter.

## 4. Refusals and Incomplete Responses

A model call can fail to produce usable output two ways, both surfaced as `LLMRefusalError`, checked **before** trusting `output_parsed`:

1. `response.status == "incomplete"` with `response.incomplete_details.reason == "content_filter"` — the whole response was blocked.
2. An individual output item's content is a `refusal` block instead of parsed text — a partial refusal within an otherwise-structured response.

Both cases must be checked explicitly: code that jumps straight to `response.output_parsed` treats a refusal as `None` — indistinguishable from an unrelated schema-validation failure — losing the information needed to log and handle it separately (docs/13 §4 `LLM_REFUSED` vs `LLM_UNAVAILABLE`).

## 5. Prompt Caching — the career profile is the cached prefix

The master career profile is identical across every CV generation; the JD is what varies. OpenAI's prompt caching is **automatic**: any request whose initial prefix (system + early messages) exactly matches a recently-seen request is served the cached portion at a quarter of the input price, with no explicit cache-control flag required (unlike some other providers). The only requirement is **prefix stability**:

```python
input = [
    {"role": "system", "content": CV_GENERATOR_INSTRUCTIONS},          # frozen
    {"role": "system", "content": serialised_career_facts},            # stable per session
    {"role": "user", "content": jd_text},                              # volatile -- goes last
]
```

This maps directly onto the real usage pattern: a batch-apply session where 5–15 CVs are generated back to back ([02_USER_JOURNEYS](02_USER_JOURNEYS.md) Journey A/C), so the facts prefix is reused across most of a session.

**Cache invalidation is a prefix byte-match**, which creates two mandatory implementation rules (`modules/cv/generator.py::_serialize_facts`):

1. Serialise career facts deterministically — `json.dumps(facts, sort_keys=True, ensure_ascii=False)`. Unsorted dict ordering silently destroys the cache.
2. Never put a timestamp, UUID, request ID, or job reference into the system messages. It belongs in the final `user` message.

Verify with `response.usage.input_tokens_details.cached_tokens` — if it is zero across consecutive generations in one session, rule 1 or 2 has been violated. This check belongs in the M3 acceptance tests, not in someone's memory.

## 6. Fallback Behaviour

| Condition | Detection | Behaviour |
|---|---|---|
| Transient error (429, 5xx, connection) | SDK auto-retries (`openai`'s default `max_retries`, exponential backoff) | Transparent; only surfaced if retries are exhausted |
| Timeout | `openai.APITimeoutError` | `503 LLM_UNAVAILABLE`; no partial CV version persisted |
| Refusal (content filter or per-item) | `response.status`/`incomplete_details` or a `refusal` content block, checked explicitly (§4) | `422 LLM_REFUSED`; logged with the reason; retry is the user's choice |
| Schema validation failure | `response.output_parsed is None` | Treated as a hard failure (`RuntimeError` → `503`); the raw response is logged for prompt debugging |
| Parser failure of any kind | caught in the background task | job untouched; no `job_parsed_data` row; CV generation still works from raw JD |

## 7. Cost Model

Per CV generation, assuming a ~4,500-token career profile, ~1,800-token JD, and ~2,500 output tokens:

| Scenario | Cached prefix | Uncached input | Output | **Total** |
|---|---|---|---|---|
| Cold (first of a session) | 4,500 @ $2.00/MTok → $0.009 | 1,800 @ $2.00/MTok → $0.0036 | 2,500 @ $8.00/MTok → $0.020 | **≈ $0.033** |
| Warm (cache hit) | 4,500 @ $0.50/MTok → $0.00225 | 1,800 @ $2.00/MTok → $0.0036 | 2,500 @ $8.00/MTok → $0.020 | **≈ $0.026** |

Per JD parse (~2,200 in, ~700 out): **≈ $0.010**.

**Projected cost of the entire V1 stabilization run** (50 jobs, ~75 CV generations of which ~40% cold, 50 parses):

```text
CV generation   30 × $0.033  +  45 × $0.026   ≈  $2.16
JD parsing      50 × $0.010                    ≈  $0.50
                                       total   ≈  $2.66
```

Under three dollars for the whole V1 proving run — even cheaper than the earlier Claude-based estimate. This matters as a design conclusion: **cost is not a constraint on this product at this scale**, so no cost-driven compromise on model choice or grounding thoroughness is justified in V1.

Controls that are still worth having, for safety rather than economy:
- Per-run token/latency/cost recorded in `cv_generation_runs` ([04_DATA_MODEL](04_DATA_MODEL.md) §5) so actual spend is observable rather than estimated.
- Cache parser output keyed by `sha256(raw_text)` — re-parsing byte-identical text is pure waste.

## 8. Prompt and Model Versioning

```text
agents/
  cv_generator/prompts/v1.md      ← CV_GENERATOR_INSTRUCTIONS
  job_parser/prompts/v1.md
```

Every run records `model_name` and `prompt_version` in `cv_generation_runs`. A prompt is never edited in place once it has produced a persisted CV version — a change means `v2.md`, so any future "this CV looks wrong" question resolves to an exact (prompt, model) pair. Adopting a new prompt or model version requires a passing run against the eval set first ([07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md) §Regression).

## 9. Latency

| Operation | Target p95 | Handling |
|---|---|---|
| JD parse | < 20 s | Background task; user never waits |
| CV generation | < 60 s | Background task with progress; per-call `timeout=90.0` seconds |
| CV section regeneration | < 30 s | Smaller output; same path |

Timeout is set per call (`responses.parse(..., timeout=timeout_s)`) rather than left at the SDK's default — a long hang on an interactive action is indistinguishable from a hung app.

## 10. Privacy Boundary

Sending career facts and JD text to OpenAI is a **deliberate third-party disclosure of PII** (name, employers, dates, achievements). It is the one place where this otherwise local-first product sends personal data off-device. This is an accepted, documented tradeoff, not an oversight — see [11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §4, which also records what is *not* sent (contact details, salary expectations, and any answer marked private).

## 11. Evaluation

Grounding, extraction, and must-have-vs-nice-to-have classification are all evaluated before being trusted in the real workflow. Definitions, dataset, and metrics: [07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md) and [12_TEST_STRATEGY](12_TEST_STRATEGY.md) §Evals.
