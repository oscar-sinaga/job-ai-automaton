# 17 — Decision Log

Architecture decisions and their consequences. Format: context → decision → consequence. Append-only; a reversed decision gets a new entry marked *Superseded*, and the original stays.

**Open decisions needing the product owner are in §2.** Mobile reachability and client approach (formerly OPEN-1/OPEN-2) are now settled — ADR-019, ADR-020 — so nothing blocks Milestone 1.

---

## 1. Decisions Made

### ADR-001 — Fixed stack is not re-litigated
*2026-08-28 · Accepted*

**Context:** Master spec §8 declares FastAPI + PostgreSQL + SvelteKit + TypeScript + Tailwind a product-owner decision, "not open for substitution unless there is a blocking technical reason."
**Decision:** Adopt as given. No evaluation of alternatives was performed, and none is warranted.
**Consequence:** Library-level choices (Alembic, SQLAlchemy, pydantic-settings, Vite) remain open; the five pillars do not.

### ADR-002 — Single-user, local-first; no auth system
*2026-08-28 · Accepted*

**Context:** One user. Master spec §24 lists "complex multi-user RBAC" as a non-goal, but three clients (web, extension, mobile) still write to the API, and mobile may be off-machine.
**Decision:** No login flow. A `users` table exists and every row carries `user_id`, but V1 resolves all requests to one implicit user. Write access is guarded by a single static `OSCAR_API_KEY` compared in constant time.
**Consequence:** Multi-user support later requires auth plumbing but **no schema migration**. The API key is a network guard, not an identity system — and it becomes inadequate the moment OPEN-1 resolves to public exposure ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §3).

### ADR-003 — Modular monolith, not microservices
*2026-08-28 · Accepted*

**Context:** Master spec §32 prefers a modular monolith absent evidence otherwise.
**Decision:** One FastAPI service with enforced module boundaries (`jobs`, `career`, `cv`, `applications`, `analytics`) and ports/adapters for LLM and storage. Import direction is enforced by `import-linter` in CI, not by convention.
**Consequence:** Future extraction of e.g. CV generation is tractable. Cross-module calls go through service functions, which costs a little indirection now and buys the option later.

### ADR-004 — In-process background tasks; no queue yet
*2026-08-28 · Accepted*

**Context:** Master spec §27 warns against a complex distributed queue if a simpler worker suffices. Workload: a handful of parses and generations per day, all idempotent.
**Decision:** FastAPI `BackgroundTasks`. No Redis, Celery, or RQ.
**Consequence:** Tasks are lost on restart and there is no retry history — accepted because every task is re-runnable from the UI. Revisit trigger is explicit and measured (OPEN-3), not aesthetic.

### ADR-005 — Status materialised in exactly one column
*2026-08-28 · Accepted*

**Context:** Master spec §10 lists status history as event-based with a materialised current status "for convenience". Both `jobs` and `applications` are plausible homes.
**Decision:** `jobs.current_status` is the sole materialised column. `applications` has **no** status column. Events remain the source of truth; the materialised column is written in the same transaction as its event.
**Consequence:** Two status columns cannot disagree, because there is only one. The inbox filters on `jobs.current_status`; post-`APPLIED` transitions arrive via `application_events` and update it.

### ADR-006 — Funnel counts are stage-reached, not current status
*2026-08-28 · Accepted*

**Context:** A job now `REJECTED` still reached `INTERVIEW`. Counting current status makes the funnel shrink as processes conclude.
**Decision:** All funnel and KPI counts derive from *first time each stage was reached*, computed from events via `v_job_stages`. Current-status breakdown is shown separately and labelled.
**Consequence:** The funnel is not strictly monotonic (assessment is optional), and the UI must render independent stage counts rather than nested subsets. Detail: [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) §D1, §4.

### ADR-007 — `SKIPPED` excluded from conversion denominators, `WITHDRAWN` included
*2026-08-28 · Accepted*

**Context:** Master spec §36 requires explicit treatment of withdrawn/skipped.
**Decision:** `SKIPPED` (chose not to apply) leaves `eligible_saved`; `WITHDRAWN` (applied, then pulled out) stays in the applied cohort.
**Consequence:** Good triage does not depress conversion — which keeps the metric from arguing against a behaviour the product wants to encourage.

### ADR-008 — Grounding is deterministic code; LLM judge is secondary only
*2026-08-28 · Accepted*

**Context:** FR-006's absolute rule and G3's zero-fabrication gate. Master spec §11 permits LLM-as-judge only as a secondary control.
**Decision:** Verification rules V1–V6 are pure functions with unit tests. Fact IDs are checked against the *retrieved set*, not the whole database. A secondary LLM judge may reject but never approve. Fail closed: unrepairable bullets are dropped; if all are dropped, no version is persisted.
**Consequence:** The core safety property is testable offline without an LLM and cannot regress through prompt drift. Some legitimate bullets will be falsely rejected — accepted, because a false rejection costs one regeneration and a false acceptance costs the product's promise.

### ADR-009 — Deterministic tag-based fact retrieval; no vector store
*2026-08-28 · Accepted*

**Context:** Retrieval must select relevant career facts. The corpus is tens of facts, not thousands.
**Decision:** Weighted tag-overlap scoring plus recency and verification bonuses. No embeddings, no vector database.
**Consequence:** Every retrieval decision is explainable to the user and adds no infrastructure. Semantic near-misses (a fact tagged `MLflow` vs. a JD asking for "experiment tracking") will be missed; mitigated by tag hygiene in M2, escalated only if evals prove it binding (OPEN-4).

### ADR-010 — `claude-opus-5` as the default model
*2026-08-28 · Superseded by ADR-025 (2026-08-28, same day — owner preference, not a technical reversal)*

**Context:** Grounding fidelity is the hard constraint. Projected total LLM cost for the entire V1 stabilization run was estimated at **≈ $8** on this provider ([06_AI_LLM_DESIGN](06_AI_LLM_DESIGN.md) §7, historical).
**Decision (as originally made):** Default `claude-opus-5` for both CV generation and parsing, behind the `LLMProvider` port, with the model as a config value.
**Why it no longer applies:** The owner asked to switch the LLM provider to OpenAI (ADR-025) before any real usage occurred — this was never triggered by a cost, quality, or reliability problem with the Anthropic adapter, which worked correctly. Left in the log rather than deleted, per this document's own append-only convention.
**What still holds from this decision:** the reasoning about cost not being a meaningful constraint at single-user scale, and about provider-specific code staying confined to one adapter file, both carried forward unchanged into ADR-025.

### ADR-011 — Career profile is the cached prompt prefix
*2026-08-28 · Accepted*

**Context:** The fact store is identical across generations; the JD varies. Real usage is batch-apply sessions of 5–15 CVs.
**Decision:** Fact store goes in `system` blocks with `cache_control` and `ttl: "1h"`; volatile content goes in `messages` after the breakpoint. Facts are serialised with `sort_keys=True`, and no timestamp/UUID may enter the system blocks.
**Consequence:** Most generations in a session become cache hits. The failure mode is silent, so an acceptance test asserts `cache_read_tokens > 0` on the second generation (R-15 in [16_RISK_REGISTER](16_RISK_REGISTER.md)).

### ADR-012 — Server derives capture completeness; clients never assert it
*2026-08-28 · Accepted*

**Context:** Mobile shares are usually URL+title only, and master spec §15 forbids pretending extraction succeeded.
**Decision:** `capture_completeness` is absent from `CaptureEnvelope` and computed server-side from the payload.
**Consequence:** A buggy client cannot mark a partial capture complete. Partial captures are surfaced as their own backlog category so they don't rot unnoticed.

### ADR-013 — Idempotency keys on capture, separate from deduplication
*2026-08-28 · Accepted*

**Context:** NFR-002 requires a mobile share retry, and retries must not create twins. This is a different problem from the same job being captured on two different occasions.
**Decision:** Client-generated `Idempotency-Key` header, stored under a partial unique index; a repeat returns the original job with 200. Deduplication remains separate, non-blocking, and flag-only.
**Consequence:** Retry is always safe. Two distinct concepts stay distinct instead of one half-solving both.

### ADR-014 — CV edits create new versions; submitted versions are immutable
*2026-08-28 · Accepted*

**Context:** US-4 requires that the exact submitted CV remain retrievable forever.
**Decision:** `PATCH /cv/{id}` creates a new version rather than mutating. A partial unique index enforces at most one submitted version per job **in the database**.
**Consequence:** Version count grows (harmless). Traceability is guaranteed by a constraint rather than by application discipline.

### ADR-015 — Real Postgres in tests, never SQLite
*2026-08-28 · Accepted*

**Context:** The schema uses enums, `text[]`, GIN indexes, and partial unique indexes.
**Decision:** Tests run against the docker-compose Postgres, isolated by per-test transaction rollback.
**Consequence:** Slightly slower and requires Docker for local testing. Avoids the worse outcome: a green test suite validating a schema that production does not have.

### ADR-016 — npm, not pnpm
*2026-08-28 · Accepted*

**Context:** pnpm is not installed on the development machine.
**Consequence:** Slower installs, larger `node_modules`. No lock-in; switchable at any time.

### ADR-017 — Python 3.12 via uv, pinned
*2026-08-28 · Accepted*

**Context:** System Python is 3.10.9; `uv` 0.9.10 is available and is the owner's preferred tool.
**Decision:** `.python-version` pins 3.12; `uv` provisions the interpreter and the environment; `uv.lock` is committed.
**Consequence:** Reproducible environments, system Python untouched, and `uv sync` is the single setup command.

### ADR-018 — Documentation pack precedes implementation
*2026-08-28 · Accepted*

**Context:** Master spec §40/§43 requires the design pack and product-owner approval before major implementation.
**Decision:** Docs 01–17 plus the Milestone 0 scaffold were produced first; no feature code was written.
**Consequence:** Milestone 1 starts from an approved design. The docs are living — decisions change here first, code second.

---

### ADR-019 — Mobile reachability: Tailscale
*2026-08-28 · Accepted (resolves former OPEN-1; unblocks M1)*

**Context:** A phone cannot reach a laptop-local API at all (§OPEN-1 as originally framed). Four options were weighed: **A** LAN IP (free, fails off-LAN — exactly when capture matters most), **B** Tailscale private mesh (data stays on-device, laptop must be awake), **C** Cloudflare Tunnel (public hostname, needs auth hardening), **D** hosted VPS (removes the awake-laptop constraint, but moves the career dossier off-device and expands privacy scope).
**Decision:** **B — Tailscale.** Bind uvicorn to the Tailscale interface (`--host 0.0.0.0` behind the mesh, not the public internet); phone and laptop join the same tailnet.
**Consequence:** Mobile capture works off-LAN without public exposure or added hosting cost. Accepted limitation: capture fails if the laptop is asleep — mitigated by the client-side retry queue (ADR-013) so nothing is lost, only delayed. Revisit toward option D only if measured usage during M6 shows the awake-laptop constraint is actually costing real captures. Detail: [09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §2, [03_SYSTEM_ARCHITECTURE](03_SYSTEM_ARCHITECTURE.md) §6, [14_DEPLOYMENT_PLAN](14_DEPLOYMENT_PLAN.md) §4.

### ADR-020 — Mobile client approach: share-shortcut now, PWA share target for V1
*2026-08-28 · Accepted (resolves former OPEN-2; unblocks M1)*

**Context:** Three options: **1** OS share shortcut → HTTP POST (~1 hour, no build pipeline), **2** PWA Web Share Target (good on Android, uncertain on iOS Safari), **3** Capacitor + native share extension (~1 week, reliable on iOS, needs a release pipeline disproportionate to a single-user tool).
**Decision:** Ship **1** immediately as the M1 zero-build bridge; build **2** as the real V1 mobile client; hold **3** as contingency requiring separate explicit approval if the M1 spike shows iOS PWA share is genuinely unworkable.
**Consequence:** M1 can prove mobile capture end-to-end on day one via the share shortcut, without waiting on PWA share-target work. The 1-day timeboxed spike in M1 ([09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §6) still runs, but to validate and refine option 2, not to choose among three unknowns from a standing start.

### ADR-021 — Browser extension bundled with esbuild, not Vite
*2026-08-28 · Accepted*

**Context:** The extension has four entry points with different runtime constraints: `background.js` is an ES-module service worker; `content.js` is injected on-demand via `chrome.scripting.executeScript({files:[...]})` and Chrome always runs such files as a classic (non-module) script, so it must be a self-contained IIFE; `popup.js`/`options.js` are plain ES modules loaded from HTML.
**Decision:** Use esbuild directly (`build.mjs`, four separate `build()` calls with per-entry `format`), not Vite as originally sketched in [08_BROWSER_EXTENSION_DESIGN](08_BROWSER_EXTENSION_DESIGN.md) §8.
**Consequence:** Each entry point gets exactly the module format it needs with no plugin. The content script reports its result via `chrome.runtime.sendMessage` rather than an `executeScript` return value, sidestepping the "a wrapped function's completion value is always `undefined` without an explicit `return`" pitfall entirely.

### ADR-022 — Local Postgres/API development runs inside WSL, not Windows-side
*2026-08-28 · Accepted*

**Context:** Docker itself runs inside the WSL2 Ubuntu distro (per the user's setup). Testing during Milestone 1 showed that Windows could not reliably reach the WSL2-forwarded `127.0.0.1:5432` (`Test-NetConnection` failed, and `alembic upgrade head` run from Windows hung) even when the container reported healthy and WSL itself could reach it instantly (`/dev/tcp/127.0.0.1/5432` succeeded). The most likely cause is WSL2's localhost port-forwarding being unreliable across long-idle gaps between separate command invocations in this environment, not a fundamental block — a continuously-running interactive WSL terminal should not hit it.
**Decision:** Run `uv`, `alembic`, `pytest`, and `uvicorn` from inside WSL (`wsl bash -lc '...'`) whenever they need the database. The Python venv lives at `~/.venvs/oscar-api` (outside `/mnt/c`) via `UV_PROJECT_ENVIRONMENT`, since `uv` cannot manage a Windows-created `.venv`'s `Scripts/` layout from Linux (permission errors on `/mnt/c`) — keep the two venvs (Windows-side `apps/api/.venv`, WSL-side `~/.venvs/oscar-api`) separate; don't try to share one.
**Consequence:** `docs/14_DEPLOYMENT_PLAN.md`'s runbook should be read as "run from a WSL terminal" for every command that touches Postgres. The web app (`npm run dev`) is unaffected and continues to run on the Windows side. If this proves to be a persistent, non-transient limitation of the actual dev machine (not just this session's tool-invocation cadence), record that finding here as a follow-up.

### ADR-023 — CV grounding does one verification pass, no automated repair-retry
*2026-08-28 · Accepted*

**Context:** [07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md) §3 describes a repair step: feed rejections back to the model for one retry before dropping a bullet.
**Decision:** V1 verifies once and drops failing bullets immediately (`modules/cv/grounding.py`) — no automated LLM repair round.
**Consequence:** More bullets get dropped instead of silently fixed by a second model call — strictly safer (never keeps an unsupported claim), just costs one extra manual regeneration occasionally instead of an automatic one. Saves an LLM round-trip per generation. Revisit if the drop rate proves annoying in real use (M6).

### ADR-024 — Eval harness lives in `apps/api/scripts/`, not a top-level `evals` package
*2026-08-28 · Accepted*

**Context:** [07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md) §6 and the original `evals/README.md` sketched `uv run python -m evals.run`, implying `evals/` at repo root is its own runnable Python package. It needs to import `oscar_api` directly to reuse the real retrieval/grounding/generator code (not reimplement it).
**Decision:** Fixtures (profiles, cases, adversarial JDs) stay at the documented `evals/cv_grounding/` location; the executable harness is `apps/api/scripts/eval_cv_grounding.py`, run via `apps/api`'s own `uv` environment.
**Consequence:** No second Python environment or path-dependency wiring needed just to import `oscar_api`. `evals/` is data-only; anyone extending the harness edits `apps/api/scripts/`. Not run in this session — no LLM provider API key was available (see [15_ROADMAP_AND_MILESTONES](15_ROADMAP_AND_MILESTONES.md) M3 status).

### ADR-025 — LLM provider switched to OpenAI (`gpt-4.1`), superseding ADR-010
*2026-08-28 · Accepted*

**Context:** The owner asked to switch the LLM provider from Anthropic to OpenAI, using an OpenAI API key instead of an Anthropic one. This is exactly the scenario the `LLMProvider` port (docs/06 §1) exists for: nothing in `modules/` imports a vendor SDK directly, so swapping providers means writing one new adapter and changing which one `modules/cv/deps.py` constructs — not touching the generator, the grounding verifier, or any test.
**Decision:** `adapters/openai_provider.py` (`OpenAILLMProvider`) replaces `adapters/anthropic_provider.py` entirely — deleted, not kept alongside, since the request was to switch, not to support both. Uses the OpenAI Python SDK's Responses API `.parse()` helper (`AsyncOpenAI().responses.parse(model=..., input=[...], text_format=SomePydanticModel)`), reading the parsed result from `response.output_parsed`. Default model: **`gpt-4.1`** ($2.00 / $8.00 per MTok, $0.50 cached-input; verified directly against OpenAI's own pricing page and the installed SDK's type stubs on 2026-08-28 — see docs/06 §2, §7). Config: `OPENAI_API_KEY` (no `OSCAR_` prefix, matching the SDK's own env var convention, same pattern `ANTHROPIC_API_KEY` used) plus `OSCAR_LLM_MODEL`/`OSCAR_LLM_PARSER_MODEL`, both now defaulting to `gpt-4.1`. `OSCAR_LLM_EFFORT` removed from settings — it was never read anywhere (a pre-existing dead setting, not something this switch broke) and `gpt-4.1` isn't a reasoning model that would use it anyway.
**What changed in the adapter's internals vs. the Anthropic version:** prompt caching is automatic (no explicit `cache_control` breakpoint — the port's `ContentBlock.cache_control` field is now a documented no-op, kept only in case a future adapter needs it); refusal detection checks `response.status == "incomplete"` + `incomplete_details.reason == "content_filter"` **and** per-item `refusal` content blocks, instead of a single top-level `stop_reason`; the port's `effort` parameter is accepted but unused by this adapter (`gpt-4.1` has no reasoning-effort concept) rather than being mapped to something that would silently change behaviour.
**Consequence:** Every test still passes unchanged (`FakeLLMProvider` never touches either SDK). The eval harness (ADR-024) and `docs/06_AI_LLM_DESIGN.md`'s cost model were updated for the new provider/pricing; the projected V1 stabilization-run cost drops from ≈$8 to ≈$2.66, reinforcing that cost was never the deciding factor for either provider at this scale. `docs/15_ROADMAP_AND_MILESTONES.md` M3 status note about "never run against a real model" still applies — this environment has no `OPENAI_API_KEY` either.

### ADR-026 — Selection-only CV pilot, reviewed versions and downloadable PDFs
*2026-11-02 · Implemented for the first real-usage pilot*

**Context:** Review reproduced an invented claim citing an unrelated valid fact,
unsupported skills passing untouched, and manual edits bypassing verification.
The six deterministic rules did not establish semantic support. Approval could
also rewind an applied job, and ordinary multi-bullet/Unicode PDFs failed.

**Decision:** Prompt `cv_generator/v2` selects/reorders complete achievement
statements. A seventh rule requires whole-statement equality after case,
whitespace, Unicode normalization and final-full-stop normalization. Each bullet
must belong to its stated experience/project; skills must be in the profile or
retrieved tags. Generation drops and reports unsupported content; edits reject
it with 422. Rewording a career fact happens in Career Profile before generating
or updating a CV. Free paraphrasing is deferred until semantic checks are evaluated.

Versions snapshot source statements, experience/project headings and CV contact
details. The UI exposes sources and asks for explicit review; approval is scoped
to the version and only promotes SAVED to READY_TO_APPLY. Other statuses are
preserved. Export requires approval, candidate name and email, and uses bundled
DejaVu fonts. An authenticated artifact route serves the saved PDF; repeated
exports reuse the same artifact and bytes. Profile changes never rewrite a version.

**Consequence:** This reduces tailoring to selection and ordering for the pilot.
Stored facts still need the owner's confirmation; this is not an independent
truth check. Before a first export, validation uses current active facts, so a
changed/deleted fact can require a new version. Previously saved PDFs remain
downloadable and reusable. Existing CVs without contact/source snapshots should
be updated from Career Profile into a new version and reviewed again. No schema
migration or real provider call is needed for these repairs.

### ADR-027 — Low-cost default and real-model fixture acceptance
*2026-11-03 · Accepted after the owner's explicit data-sharing and low-cost instruction*

**Decision:** Use `gpt-6-luna` for the CV model default, superseding only ADR-025's
model choice. It is available to the supplied project and supports Responses
structured output. Set reasoning to `none`, output to 4,096 tokens by default,
one request attempt and no automatic upgrade to a more expensive model. The
validated output limit is 512–16,000; Compose forwards model/budget overrides.
Non-reasoning models omit the reasoning parameter; original GPT-5 variants map
`none` to their supported `minimal` setting when explicitly selected.

**Evidence:** Four approved public-fixture API cases passed with prompt v2:
positive MLOps, metric inflation, adjacent technology, and JD prompt injection.
24 claims/skills were checked, with no rejected claims in this sample. Total
usage was 4,289 input and 561 output tokens. Actual outputs, timing and tested
source hashes are committed in
[the eval result](../evals/cv_grounding/results/2026-11-03_gpt-6-luna.json).
Standard rates on the test date were $0.10/M input, $0.50/M output and $0.125/M
cache writes, per the [official model page](https://developers.openai.com/api/docs/models/gpt-6-luna).
The token-price estimate is below $0.001, not a billing statement.

**Limits:** This establishes fixture acceptance for the technical MVP. Real
career facts, physical-phone capture and M6's actual application/time targets
remain separate. OPEN-5 is not closed by permission to send public test fixtures.

### ADR-027 — Source-owned CV metadata and reference-style export
**Date:** 2026-11-03. Real-profile testing exposed missing education in export,
false gap suggestions caused by absent profile metadata, and model confusion
between concurrent roles at one employer. Freeze owner-entered education,
credentials and location in each version, and render them in the reference-style
single-column A4 template. Derive selected bullets' role/project placement from
unambiguous retrieved source parents before running the unchanged claim verifier.
Supply education/skills/dates, excluding contacts, to `cv_generator/v3` for gap
assessment. Gap suggestions remain review points rather than eligibility decisions.
See [real-profile acceptance and limits](22_REAL_PROFILE_ACCEPTANCE.md).

## 2. Open Decisions

### OPEN-3 — Durable job queue
Deferred by ADR-004. Revisit if CV generation p95 exceeds 60 s or lost-on-restart tasks become a real annoyance during M6.

### OPEN-4 — Embedding-based fact retrieval
Deferred by ADR-009. Revisit if eval `fact_recall` falls below 80% after M2's tag hygiene work.

### OPEN-5 — LLM provider data-retention posture
Career facts and JD text are sent to OpenAI (ADR-025; [11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §4). The owner should review the account's data-retention configuration and record the accepted posture here.

### OPEN-6 — Production hosting
Not needed for V1 ([14_DEPLOYMENT_PLAN](14_DEPLOYMENT_PLAN.md) §7). Becomes live if OPEN-1 resolves to D, and would require revising [11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §3 first.
