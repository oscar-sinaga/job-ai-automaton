# 15 — Roadmap & Milestones

Method: **vertical slices** (master spec §38). Each milestone ends with something usable on real jobs, never with "the database layer is done". Estimates assume solo part-time work.

```text
M0 Foundation ──► M1 Capture ──► M2 Career Profile ──► M3 CV ──► M4 Tracking ──► M5 Analytics ──► M6 Stabilization ──► V1
   (done)          (done)         (build done)       (build done) (build done)   (build done)      ~4 wks real usage
```

All five build milestones are done as of this session. What remains before V1 is **M6 — real usage** (see below): populating the career profile with real data, actually job-hunting with the tool, and measuring against the V1 Definition of Done. None of that can be simulated in a build session — it requires the product owner's own time, real jobs, and (for CV generation) a real `OPENAI_API_KEY`.

Total to V1: roughly **2.5–3 months**, matching the master spec's "genuinely usable within a few months".

---

## Milestone 0 — Foundation ✅ *(this session)*

Repo structure · uv-managed FastAPI app with `/health` · SvelteKit + TS + Tailwind shell with the 7 route stubs · Postgres via docker-compose · Alembic with an empty baseline revision · pytest harness · CI (lint, types, migrate up/down, test, secret scan) · this documentation pack.

**Exit criteria:** `/health` returns 200 with `db: ok`; `pytest` green; `alembic upgrade head` then `downgrade -1` clean; `npm run build` succeeds; CI passes.

**Deliberately absent:** every domain table, every feature. Milestone 0 proves the toolchain, not the product.

---

## Milestone 1 — Capture ✅ *(this session)*

The first genuinely useful slice: jobs stop getting lost.

- `CaptureEnvelope` contract + `POST /api/v1/jobs/capture` with idempotency (`Idempotency-Key`) and server-derived completeness (ADR-012)
- `users`, `sources`, `companies`, `role_categories`, `jobs`, `job_raw_snapshots`, `job_events` tables (migration `0002_jobs_capture`)
- Dedupe key computation (URL canonicalisation + source-ID extraction + company/title fallback); duplicates flagged via `duplicate_of_job_id`, never blocked
- `POST /jobs/{id}/snapshots` (enrichment, append-only) and the paste-text / manual-URL fallbacks in the Job Inbox page
- Job Inbox (`/jobs`): list, filter by status/source/search, cursor pagination, capture form; Job Detail (`/jobs/[id]`): raw JD, timeline, corrections, enrichment
- Browser extension (`apps/extension`): MV3, generic 4-branch extraction heuristic, one-click save via popup, settings page for API key/base URL
- Mobile: PWA Web Share Target (`apps/web/static/manifest.webmanifest` + `/share-target` route) + OS-share-shortcut instructions (`apps/mobile/README.md`) per ADR-019/020

**Exit criteria met (build/test, not yet real-usage — that's M6):** 39 tests passing (unit: dedupe, completeness derivation; integration: capture × 4 methods, idempotency, duplicates, enrichment, inbox filters/pagination/patch) against real Postgres; `ruff`/`mypy` clean; migration verified up→down→up; `svelte-check`/`npm run build` clean for web and extension.

**Deferred to the M1 spike (real-device validation, not yet run):** confirming the PWA share target and OS-share-shortcut actually work end-to-end on Oscar's phone (ADR-019/020) — the server-side code path is tested, but real-device behavior needs a physical phone, which this build/test pass cannot substitute for.

**Vertical slice proved:** save one job end-to-end and see it in the inbox.

---

## Milestone 2 — Career Profile ✅ build *(this session)* — data entry still pending

- `career_*` tables + `application_profiles` (migration `0003_career_profile`), with the `metric_verified` and single-parent (`num_nonnulls`) CHECK constraints, plus soft-delete on achievements
- CRUD API for all six nested collections + the 1:1 application profile, each with a proactive service-layer validation (not just a raw DB constraint surfacing as a 500) for the metric and single-parent rules
- Career Profile edit UI (`/career-profile`) — plain forms per section, no polish, tag entry as comma-separated fields
- 8 integration tests covering the constraints, soft delete, and round-tripping tags

**Exit criteria met (build):** 47 total API tests passing; `ruff`/`mypy` clean; migration verified up→down→up; `svelte-check`/`npm run build` clean.

**Not yet done — the actual deliverable of this milestone:** populating Oscar's *real* profile (all experiences, ≥ 20 tagged achievements, every metric explicitly marked verified or not). The code lets this happen; nobody has sat down and done it yet. Nothing in M3 (grounding, retrieval) can be meaningfully tested end-to-end without real data here — nagged as R-14 in [16_RISK_REGISTER](16_RISK_REGISTER.md).

**Note on effort:** the build is small; the *data entry* is 1–2 hours of careful work and is the real deliverable. Nothing downstream — grounding, tailoring, fit score, skill-gap analysis — can be better than this data. Rushing this milestone caps the quality of the entire product.

---

## Milestone 3 — CV Generation ✅ build *(this session)* — highest-risk milestone

- `LLMProvider`/`Storage` ports + `OpenAILLMProvider`/`LocalFileStorage` adapters (async, structured output via the Responses API's `.parse()`, automatic prompt caching)
- Deterministic fact retrieval (`modules/cv/retrieval.py`: tag-overlap scoring + recency/verified bonuses, keyword-matched against the JD since no parser exists yet)
- `cv_versions` (partial-unique one-submitted-per-job), `cv_generation_runs`, `cv_artifacts` tables (migration `0004_cv`)
- **Grounding verifier V1–V6** (`modules/cv/grounding.py`) with 17 unit tests against in-memory fixtures, plus 9 integration tests through the real API (success, partial rejection, all-rejected, LLM-unavailable, edit-creates-new-version, approve, export, mark-submitted-exclusivity)
- CV Review UI (`/cv/[id]`): per-bullet fact-ID provenance, remove-a-bullet (creates a new version), approve, export, mark submitted; wired into Job Detail's "Generate CV" action
- PDF export via `fpdf2`, decoupled from generation (export failure never touches the `CVVersion` row)
- Eval harness (`apps/api/scripts/eval_cv_grounding.py`) + 1 positive + 2 adversarial fixture cases

**Simplifications recorded as decisions, not gaps:** no automated repair-retry before dropping a rejected bullet (ADR-023 — strictly safer, not less safe); no secondary LLM-judge pass yet (the deterministic checks are the primary control and are sufficient alone per docs/07 §3); `job_parser` agent not built (P1, non-blocking by design — requirement extraction instead keyword-matches the JD against the profile's own vocabulary).

**Exit criteria met (build/test):** 73 total API tests passing (0 failures after two real bugs were found and fixed — see below); `ruff`/`mypy` clean; migration verified up→down→up; `svelte-check`/`npm run build` clean.

**Not yet met — needs a real `OPENAI_API_KEY` and real profile data, neither available in this session:** the eval suite has never actually run against a real model (fabrication rate / verifier recall are therefore unmeasured against real LLM output, though the verifier itself is fully unit-tested against adversarial *fixtures*); "5 real CVs generated" and "median generate→export under 2 minutes" cannot be assessed without real usage. Run `apps/api/scripts/eval_cv_grounding.py` against both adversarial cases before trusting this with a real application.

**Bugs found and fixed while building this milestone** (kept here as the kind of thing worth watching for when extending grounding logic): (1) a reused SQLAlchemy `ENUM` object triggered a duplicate `CREATE TYPE` in the M1 migration — fixed via `create_type=False` after explicit creation; (2) V2 (`check_metric_match`) was treating *any* number in a bullet as a metric needing a backing fact — including "8 years of experience" — which made V6 (date consistency) unreachable; fixed by excluding duration-context numbers from the metric check, since V6 already covers those.

**Why highest-risk:** it holds G3 (the non-negotiable goal) and master spec §41's only *critical* product risk. Sequencing held as planned: the verifier was written and unit-tested against fabricated fixtures before the real generator was wired up, so its guarantees never depend on the generator behaving well.

---

## Milestone 4 — Application Tracking ✅ build *(this session)*

- `applications`, `application_events`, `application_answers` tables (migration `0005_applications`); no `applications.current_status` column — `jobs.current_status` stays the sole materialized status (ADR-005)
- Status state machine (`modules/applications/state_machine.py`) rejecting illegal transitions with `409 ILLEGAL_TRANSITION`; `INTERVIEW_RECEIVED` self-loop for multi-round interviews; `INTERVIEW_COMPLETED` as a status-preserving informational event
- One-click actions in the Job Detail UI: Mark as Applied (creates the `Application`, optionally links a submitted CV version), Assessment/Interview/Final/Rejected/Offer/Withdraw (state-aware — only the currently-legal next steps are shown), Skip/Un-skip (pre-application, no `Application` row needed)
- Submitted-CV linkage reuses the M3 `is_submitted` exclusivity constraint; `POST /applications` and CV's own `mark-submitted` both go through it
- Job-scoped application lookup (`GET /jobs/{id}/application`) so the jobs module stays a dependency leaf while the UI can still show tracking state

**Exit criteria met (build/test):** 27 new tests (table-driven state-machine sweep across all 11 statuses × 9 event types, plus explicit spot-checks against docs/04 §6, plus integration tests for the full happy path, multi-round interviews, illegal transitions, CV linkage, skip/unskip); 206 total tests passing; `ruff`/`mypy` clean; migration verified up→down→up; `svelte-check`/`npm run build` clean.

**Not yet met:** "10 real applications tracked" needs real usage (M6).

**Vertical slice proved:** track one application end-to-end, with the state machine actually rejecting an illegal transition rather than silently accepting it.

---

## Milestone 5 — Analytics ✅ build *(this session)* — the last P0 milestone

- `v_job_timeline` and `v_job_stages` views (migration `0006_analytics_views`) — the merged event stream and per-job "first time each stage was reached" that every formula reads
- All formulas from [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) in `modules/analytics/queries.py` — KPIs, funnel, conversion (D1–D5 semantics), backlog, trends (timezone-bucketed), source/role breakdown, productivity
- Dashboard (`/`): KPIs, funnel bar chart, conversion percentages, backlog, action queue; Analytics page (`/analytics`): trends chart, source/role tables, productivity, honest "skills not built yet" note
- Action queue with working deep links (`/jobs?missing_cv=1` etc.) — required extending `GET /jobs` with `completeness`/`older_than`/`missing_cv`/`needs_action` filters (kept import-free of the cv/applications modules per ADR — jobs stays a dependency leaf)
- Sample-not-market disclosure on every analytics response, not just the dashboard

**Exit criteria met:** 10 new tests building a hand-counted fixture (a skipped job, a withdrawn application, a job rejected after reaching interview, a job that skips assessment entirely, a 2-round interview, and a duplicate) and asserting every formula against numbers computed by hand in the test comments, not derived from the code under test; every action-queue count verified equal to the length of the list its link returns; 216 total tests passing; `ruff`/`mypy` clean; migration verified up→down→up; `svelte-check`/`npm run build` clean.

**A real bug this exit criterion caught:** the backlog SQL excludes duplicate jobs (docs/10 D2) but the newly-added `missing_cv`/`needs_action` list filters initially didn't — the action-queue count and its link's result set disagreed by exactly the duplicate. Fixed by excluding duplicates in those two filters; documented in code as a decision the two general-purpose filters (`completeness`, `older_than`) don't currently make (they stay duplicate-inclusive like the plain `status` filter), flagged as a spot to recheck if M6 usage ever produces a mismatch there too.

**Vertical slice proved:** show one funnel metric that is actually correct — and prove it with a fixture were it would have been easy to get subtly wrong.

---

## Milestone 6 — Stabilization (~4 weeks of real usage)

Not a build milestone — a *usage* milestone. The product is used for real job hunting and fixed where it hurts.

- Reach ≥ 50 real jobs captured and ≥ 25 real applications tracked
- **Manually time** human active minutes per application on a sample (the north-star metric is not derivable from stored events — see [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) §9)
- Every real-world grounding near-miss added as a new adversarial eval case
- Weekly review of the signals in [13_OBSERVABILITY](13_OBSERVABILITY.md) §6
- Fix by measured pain, not by backlog order

**Exit criteria = the V1 Definition of Done** ([01_PRD](01_PRD.md) §13): ≥50 jobs, ≥25 applications, median CV prep < 2 min, human active time 3–5 min/application, **zero** known fabricated claims in exported CVs, funnel and backlog verified.

Only after this does V2 work begin (master spec §37).

---

## Dependency Order

```text
M1 Capture ──────────┐
                     ├──► M3 CV ──► M4 Tracking ──► M5 Analytics ──► M6
M2 Career Profile ───┘
```

M1 and M2 are independent and could run in parallel. M3 needs both (facts + raw JD). M5 needs M4's events to have anything to aggregate. Nothing in M3–M5 can be usefully started before M2's real data exists — which is why M2's data entry is on the critical path despite its small code footprint.

## Decision Gates

| Gate | Decision | Informed by |
|---|---|---|
| During M1 | confirm ADR-019/020 (Tailscale + share-shortcut → PWA) against real behaviour, or trigger the documented fallback | the M1 spike |
| During M3 | whether tag-based retrieval has adequate recall (OPEN-4) | `fact_recall` from the eval suite |
| After M3 | whether to keep `gpt-4.1` for parsing or trade down | measured parse quality + cost |
| After M5 | whether background tasks need a durable queue (OPEN-3) | CV generation p95 latency |
| After M6 | what V2 is | see below |

## Choosing V2 (not now)

V2 priorities are **chosen from Milestone 6 data**, not guessed today. The rule from user-plan §17:

| If the measured bottleneck is… | Then V2 is… |
|---|---|
| filling application forms | P2 autofill |
| reviewing/fixing generated CVs | better retrieval and grounding, not autofill |
| too few jobs entering the funnel | capture/discovery improvements |
| one specific ATS being painful | that ATS's adapter (P3) |
| many saved, few applied | backlog workflow and nudges |

Committing to autofill or ATS adapters before M6 produces data would be exactly the speculative infrastructure Decision Rule 3 forbids.
