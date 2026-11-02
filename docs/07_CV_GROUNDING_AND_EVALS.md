# 07 — CV Grounding & Evals

**This is the safety-critical document of the pack.** FR-006 states the absolute rule — *no unsupported claims* — and G3 in [01_PRD](01_PRD.md) makes zero fabricated claims a hard release gate that outranks speed and cost. Master spec §35 designates this design as critical.

Not implemented in Milestone 0. Binding design for Milestone 3.

---

## Current pilot policy — 2026-11-02

[ADR-026](17_DECISION_LOG.md) temporarily narrows the rewording policy described
below: prompt v2 selects complete stored achievement statements. Valid fact IDs
alone cannot prove semantic support. Whole-statement matching, parent validation,
skills validation and validation of manual edits now supplement V1–V6. The owner
reviews sources before approving each version for export. Source statements and
presentation details are snapshotted into the version. Free paraphrasing and the
secondary semantic judge remain future work requiring real-model evaluation.

## 1. Threat Model

The failure this system exists to prevent: **a plausible, fluent, well-formatted CV bullet that describes something Oscar never did**, submitted to a real employer under his name. Consequences are reputational and potentially disqualifying, and the failure is *invisible* at review time precisely because the output is fluent.

Three ways it happens:

| Failure mode | Example | Defence |
|---|---|---|
| Whole-cloth invention | "Led a team of 8 engineers" when no fact mentions leading anyone | Fact-ID citation requirement (V1) |
| Metric inflation | Fact says "improved latency"; output says "improved latency by 70%" | Verified-metric rule (V2/V3) |
| Adjacent-technology drift | Profile has Docker; JD wants Kubernetes; output claims Kubernetes | Technology allowlist (V4) |

All three are addressed by **deterministic code**, not prompt wording. A prompt is a request; a verifier is a guarantee.

## 2. Career Fact Store

Facts are rows in `career_achievements`, `career_experiences`, `career_skills`, `career_projects` ([04_DATA_MODEL](04_DATA_MODEL.md) §3), each addressable by a stable string ID used in prompts and provenance:

```text
ach_41   → career_achievements.id = 41
exp_7    → career_experiences.id = 7
skl_12   → career_skills.id = 12
prj_3    → career_projects.id = 3
```

The critical field is `metric_verified`: an achievement may carry `metric_value = "reduced p95 latency 320ms → 90ms"` but until the user marks it verified, **no number from it may reach a CV**. This makes the "don't inflate metrics" rule a data property rather than a judgement call.

## 3. Pipeline

```text
 ┌─ 1. Requirement extraction ────────────────────────────────────┐
 │  parsed_data.required_skills/preferred_skills if available,     │
 │  else keyword extraction from raw JD text                       │
 └────────────────────────────────┬───────────────────────────────┘
                                  ▼
 ┌─ 2. Fact retrieval (deterministic, explainable) ───────────────┐
 │  score each fact, select top-N, cap total tokens                │
 │  → RETRIEVED_SET: {fact_id: fact}   ← the ONLY facts the model  │
 │                                        is allowed to cite       │
 └────────────────────────────────┬───────────────────────────────┘
                                  ▼
 ┌─ 3. LLM drafting (structured output) ──────────────────────────┐
 │  each bullet MUST carry supporting_fact_ids                     │
 └────────────────────────────────┬───────────────────────────────┘
                                  ▼
 ┌─ 4. Deterministic verification (V1–V6 below) ──────────────────┐
 │  per bullet: PASS / REJECT(reason)                              │
 └────────────────────────────────┬───────────────────────────────┘
                                  ▼
 ┌─ 5. Secondary LLM judge (drift only, never the sole gate) ─────┐
 │  NOT YET BUILT (V1) — deterministic checks (V1–V6) are the      │
 │  primary control and are sufficient on their own; this is an    │
 │  enhancement, not a gap in the safety guarantee                 │
 └────────────────────────────────┬───────────────────────────────┘
                                  ▼
 ┌─ 6. Repair: one retry with rejections as feedback ─────────────┐
 │  SIMPLIFIED (V1, ADR-023): no automated retry — reject →         │
 │  DROP the bullet immediately (fail closed; strictly safer,      │
 │  just costs an occasional manual regeneration instead)          │
 └────────────────────────────────┬───────────────────────────────┘
                                  ▼
 ┌─ 7. Persist version + grounding_report → human review UI ──────┘
```

### Step 2 — retrieval scoring

V1 uses deterministic tag scoring, not embeddings. No vector store, no extra infrastructure, and — decisively — every retrieval decision is explainable to the user:

```python
def score(fact, requirements) -> float:
    s  = 3.0 * overlap(fact.skill_tags,      requirements.skills)
    s += 3.0 * overlap(fact.technology_tags, requirements.technologies)
    s += 1.5 * overlap(fact.domain_tags,     requirements.domains)
    s += 1.0 if fact.verification_status == "verified" else 0.0
    s += recency_bonus(fact.date_range)          # 0.0 … 1.0, decays over ~5 years
    return s
```

Selection: top 6 facts per relevant experience, top 30 overall, hard cap ~4,500 tokens (the cached prefix budget in [06_AI_LLM_DESIGN](06_AI_LLM_DESIGN.md) §5). Facts are always sent with their IDs and their `metric_verified` flag.

Known limitation: keyword/tag overlap misses semantic matches (a fact tagged `MLflow` won't score against a JD asking for "experiment tracking"). Mitigation for V1 is tag hygiene during profile authoring; upgrading to embeddings is deferred until evals show recall is actually the binding constraint (OPEN-4 in [17_DECISION_LOG](17_DECISION_LOG.md)).

### Step 4 — verification rules

Each rule is a pure function over `(bullet, retrieved_set, profile)` and has its own unit tests:

| ID | Rule | Rejection reason |
|---|---|---|
| V1 | Every `supporting_fact_id` is non-empty and present in `RETRIEVED_SET` | `NO_SUPPORTING_FACT` / `FACT_NOT_RETRIEVED` |
| V2 | Every number in the bullet text appears in a cited fact's `metric_value` | `METRIC_MISMATCH` |
| V3 | Any cited metric must have `metric_verified = true` | `UNVERIFIED_METRIC` |
| V4 | Every technology/skill term in the bullet appears in cited facts' tags **or** the profile's skill list | `UNKNOWN_TECHNOLOGY` |
| V5 | No company/employer name appears that is not in `career_experiences` | `UNKNOWN_EMPLOYER` |
| V6 | Any duration/date claim is consistent with the cited experience's date range | `DATE_INCONSISTENT` |

V1 is checked against the **retrieved set, not the whole database.** A fact ID that exists in the DB but was never given to the model indicates the model recalled or guessed rather than grounded — that is a fabrication signal, and accepting it would defeat the entire mechanism.

V4 needs a term extractor over a known-technology vocabulary (seeded from the profile's own skills plus a static list). It is intentionally biased toward over-flagging: a false rejection costs one regenerated bullet, a false acceptance costs the product's core promise.

### Step 5 — secondary judge

A second LLM call asks: *"Does this bullet assert anything not stated in these facts? Answer with a structured verdict."* Used only to catch paraphrase drift that V1–V6 cannot see (e.g. "architected" where the fact says "contributed to"). It can **reject** but never **approve** — a bullet that fails V1–V6 is not rescued by a judge verdict (master spec §11: LLM-as-judge is a secondary control, never the sole control).

### Step 6 — repair, then fail closed

One retry, with the specific rejections fed back as constraints. Still rejected → the bullet is dropped and recorded in `grounding_report.rejections`. If *every* bullet is rejected, no CV version is persisted and the API returns `422 GROUNDING_FAILED` ([05_API_DESIGN](05_API_DESIGN.md) §1) rather than saving an empty CV.

## 4. What the Generator May and May Not Do

| May | May not |
|---|---|
| Select which facts to include | Invent experience, employers, or projects |
| Reorder experiences, bullets, skills | Add skills or technologies absent from the profile |
| Reword and condense a fact's statement | Introduce or round any number |
| Combine two facts into one bullet (citing both) | Extend durations or seniority |
| Emphasise a fact's JD-relevant aspect | Claim certifications not in the profile |
| Report unmet JD requirements in `missing_requirements` | Silently paper over an unmet requirement |

## 5. Provenance Output

The contract that makes review possible (master spec §11 example, stored in `cv_versions.sections`):

```json
{ "bullet": "Developed production scoring APIs using FastAPI.",
  "supporting_fact_ids": ["ach_41", "ach_44"] }
```

The CV Review UI renders each bullet with its cited facts one click away, so a human check is "does this fact say that?" rather than "do I remember doing this?".

## 6. Eval Dataset

```text
evals/cv_grounding/
  profiles/oscar_sanitised.json        # a realistic fact store
  cases/
    001_mlops_engineer/{jd.txt,expected.json}
    002_data_scientist/{jd.txt,expected.json}
    ...
  adversarial/
    a01_metric_inflation/              # JD baits an unverified number
    a02_adjacent_tech/                 # JD demands Kubernetes; profile has only Docker
    a03_seniority_stretch/             # JD wants 8 years; profile has 4
    a04_invented_leadership/           # JD emphasises team leadership
    a05_phantom_certification/         # JD requires a cert not held
```

Positive cases assert that genuine, relevant facts are retrieved and used. Adversarial cases assert that the bait is **rejected** — they are the ones that actually protect G3, and every real-world near-miss found during stabilization gets added as a new adversarial case.

## 7. Eval Metrics

| Metric | Definition | Target |
|---|---|---|
| **Fabrication rate** (primary) | fabricated claims surviving verification / total claims | **0** |
| Verifier recall | injected fabrications correctly rejected / injected fabrications | 100% |
| Verifier precision | legitimate bullets wrongly rejected / legitimate bullets | < 5% |
| Fact recall | relevant available facts that appear in output / relevant available facts (human-judged) | > 80% |
| Claim-rejection rate (production) | `claims_rejected / claims_checked` per run, from `grounding_report` | monitored; a rising trend signals prompt or retrieval regression |

Fabrication rate and verifier recall are **gates** (a failing run blocks adoption). Precision and fact recall are quality signals — worth improving, never worth trading safety for.

## 8. Regression Discipline

Any change to a prompt version, model, retrieval scoring function, or verification rule must run the full eval set first. A change that lowers verifier recall below 100% is not adopted regardless of other improvements. `cv_generation_runs` stores `(model_name, prompt_version)` per run precisely so a production anomaly can be traced back to a specific configuration ([06_AI_LLM_DESIGN](06_AI_LLM_DESIGN.md) §8).

## 9. Human Review Remains the Final Gate

Automated grounding reduces review burden; it does not remove the checkpoint. The user always previews before export, can edit or delete any bullet, and — because edits create a new version rather than mutating one ([05_API_DESIGN](05_API_DESIGN.md) §5) — the reviewed-and-sent artifact stays exactly reproducible. No path exists in V1 where a generated CV reaches an employer without human review.
