# 03 — System Architecture

**Style: modular monolith.** One FastAPI service, one PostgreSQL database, one SvelteKit web client, plus two thin capture clients. Master spec §32 mandates preferring this over microservices for V1; at single-user scale a distributed design would add failure modes without removing any.

---

## 1. Component Diagram

```text
   ┌──────────────────────────┐        ┌──────────────────────────┐
   │  Browser Extension (MV3) │        │  Mobile Share Target     │
   │  apps/extension · TS     │        │  apps/mobile · see doc 09│
   │  activeTab only          │        │  partial payloads OK     │
   └────────────┬─────────────┘        └────────────┬─────────────┘
                │  POST /api/v1/jobs/capture         │
                │  X-API-Key: <local token>          │
                └──────────────┬─────────────────────┘
                               ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                  FastAPI backend  (apps/api)                 │
   │                                                              │
   │   routers ──► services ──► repositories ──► SQLAlchemy       │
   │                                                              │
   │   modules:  jobs │ career │ cv │ applications │ analytics    │
   │   ports:    LLMProvider │ Storage │ Clock                    │
   └───┬─────────────────────┬──────────────────────┬─────────────┘
       │                     │                      │
       ▼                     ▼                      ▼
  ┌──────────┐      ┌─────────────────┐    ┌──────────────────┐
  │ Postgres │      │ File storage    │    │ OpenAI API       │
  │ 16       │      │ var/storage/    │    │ (gpt-4.1)        │
  │          │      │ CV PDFs         │    │ via LLMProvider  │
  └──────────┘      └─────────────────┘    └──────────────────┘
       ▲
       │  (read + write, same service)
       │
   ┌───┴──────────────────────────────────────────────────────────┐
   │        SvelteKit web app  (apps/web)                         │
   │        Dashboard · Inbox · Job Detail · CV Review ·          │
   │        Career Profile · Analytics · Settings                  │
   │        talks to the API over HTTP only (no direct DB access)  │
   └──────────────────────────────────────────────────────────────┘
```

Note the direction of the bottom edge: **the web app is a client of the API**, never of the database. The API is the only writer to Postgres and the only holder of the LLM key.

## 2. Module Boundaries and Dependency Rules

Inside `apps/api/src/oscar_api/`:

```text
modules/
  jobs/          capture, raw snapshots, parsed data, dedupe, job events
  career/        profile, experiences, projects, skills, achievements (the fact store)
  cv/            generation runs, versions, grounding validation, PDF export
  applications/  application records, status transitions, application events
  analytics/     read-only aggregation queries
ports/           LLMProvider, Storage, Clock  (interfaces only)
adapters/        openai_provider.py, local_storage.py  (implementations)
core/            config, db session, logging, errors, event helpers
```

**Allowed dependency direction:**

```text
analytics ──reads──► (all module tables, read-only)
cv ────────────────► career (read facts), jobs (read raw JD)
applications ──────► jobs (read), cv (read version being submitted)
jobs ──────────────► (nothing; leaf)
career ────────────► (nothing; leaf)
every module ──────► core, ports
adapters ──────────► ports  (never the reverse)
```

Rules that keep this honest:
- No module imports another module's `repositories/` — only its service-layer functions.
- Nothing in `modules/` imports from `adapters/`; they depend on `ports/` and receive an implementation via dependency injection. This is what makes the LLM provider and storage swappable, and what makes tests able to run with fakes instead of network calls.
- `analytics` is read-only by convention and never writes events.
- Cycles are a build failure, not a code-review opinion (enforced by an import-linter check in CI once modules exist — see [12_TEST_STRATEGY](12_TEST_STRATEGY.md)).

## 3. Critical Request Flows

### 3.1 Capture (desktop or mobile)

```text
client                      API                            Postgres
  │  POST /api/v1/jobs/capture  (CaptureEnvelope)
  ├────────────────────────────►│
  │                             │ validate envelope
  │                             │ derive source from URL host
  │                             │ compute dedupe key
  │                             ├── BEGIN ──────────────────►│
  │                             │   INSERT jobs               │
  │                             │   INSERT job_raw_snapshots  │
  │                             │   INSERT job_events(JOB_SAVED)
  │                             ├── COMMIT ─────────────────►│
  │  201 {job_id, capture_completeness, duplicate_of_job_id?}
  │◄────────────────────────────┤
  │                             │ BackgroundTask: parse JD (best-effort)
```

The three inserts are one transaction: a job can never exist without its raw snapshot or its `JOB_SAVED` event. Parsing happens **after** the response, so parser latency and parser failure can never affect capture (FR-003, FR-004, NFR-002).

### 3.2 Grounded CV generation

```text
POST /api/v1/jobs/{id}/generate-cv
  │
  ├─ load career facts (career module) ──┐
  ├─ load latest raw snapshot (jobs) ────┤
  ├─ load parsed data if present ────────┤
  │                                      ▼
  │                          retrieve relevant facts (deterministic scoring)
  │                                      ▼
  │                          LLMProvider.generate_cv(facts, jd)
  │                          → structured output, each bullet cites fact_ids
  │                                      ▼
  │                          verify claims (deterministic; fail closed)
  │                                      ▼
  │              ┌───────── all bullets valid ──────────┐
  │              ▼                                       ▼
  │   INSERT cv_version                        drop/flag invalid bullets,
  │   INSERT cv_generation_run(grounding_report)  record rejection reasons
  │   INSERT job_events(CV_GENERATED)
  │
  └─ 201 {cv_version_id, grounding_report, missing_requirements[]}
```

Detail in [07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md). Architecturally the point is that **verification is code, not a prompt** — it lives in `modules/cv/grounding.py` and is unit-testable without an LLM.

### 3.3 Status change

```text
POST /api/v1/applications/{id}/events   {event_type: "INTERVIEW_RECEIVED"}
  │
  ├─ load current status
  ├─ assert transition is legal (state machine in doc 04)
  ├─ BEGIN
  │    INSERT application_events(...)
  │    UPDATE applications.current_status
  │  COMMIT
  └─ 200 {current_status, event_id}
```

Events are the source of truth; `current_status` is a materialized convenience column written in the same transaction. Analytics reads events, never only the materialized column ([10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md)).

## 4. Authentication and Client Access

V1 is single-user and local-first, so there is no login flow. But the API is still reachable by three different clients, and one of them (mobile) may be off-machine — so it cannot be unauthenticated:

| Client | Auth | Transport |
|---|---|---|
| SvelteKit web app | same-origin via dev proxy; API key injected server-side | `localhost` |
| Browser extension | static API key in extension options storage, sent as `X-API-Key` | `localhost` + CORS allowlist for the extension origin |
| Mobile share target | same static API key | **requires a reachable host — see §6** |

The API key is a single random secret from `OSCAR_API_KEY` in `.env`, compared with `secrets.compare_digest`. This is deliberately minimal: it is not a user-identity system, it is a "don't accept writes from anything else on the network" guard. A `users` row exists in the schema for future-proofing but V1 resolves every request to one implicit user (ADR-002 in [17_DECISION_LOG](17_DECISION_LOG.md)).

## 5. Background Work

V1 uses FastAPI `BackgroundTasks` in-process for: JD parsing, CV generation, PDF rendering. No Redis, no Celery, no RQ. Justification: single user, a handful of tasks per day, all idempotent and retryable from the UI. Master spec §27 explicitly permits this.

The trigger to revisit is concrete: if CV generation p95 exceeds ~60 s, or if a server restart mid-task becomes a real annoyance, introduce a durable queue then. Tracked as OPEN-3 in [17_DECISION_LOG](17_DECISION_LOG.md) so it is a measured decision rather than a default.

## 6. Deployment Topology and the Mobile Reachability Problem

Local dev topology:

```text
laptop
 ├── docker compose: postgres:16   → localhost:5432
 ├── uv run uvicorn (apps/api)     → localhost:8000
 └── npm run dev  (apps/web)       → localhost:5173  (proxies /api → :8000)
```

**Problem:** FR-002 (mobile capture) is P0, but a phone cannot reach `localhost:8000` on the laptop. Options, in ascending cost:

| Option | Works off-LAN | Cost | Notes |
|---|---|---|---|
| A. Same-LAN local IP (`http://192.168.x.x:8000`) | No | ~0 | Fine at home; fails on mobile data — i.e. fails exactly when capture matters most |
| B. Tailscale (or similar private mesh) | Yes | low | Phone + laptop on a private network; no public exposure; laptop must be awake |
| C. Cloudflare Tunnel to the laptop | Yes | low | Public hostname, must add real auth hardening |
| D. Host the API + DB on a small VPS / managed Postgres | Yes | ongoing $ | Removes the "laptop must be awake" constraint; raises privacy scope (career data off-device) |

**Decided: B (Tailscale) for V1** (ADR-019 in [17_DECISION_LOG](17_DECISION_LOG.md)), keeping the API private and the data on Oscar's machine, with D reconsidered only if "laptop asleep" turns out to block real capture. See also [14_DEPLOYMENT_PLAN](14_DEPLOYMENT_PLAN.md).

## 7. Failure Handling

| Failure | Detection | Behaviour | Guarantee preserved |
|---|---|---|---|
| Parser exception/timeout | logged with `error_type` | job untouched, no `job_parsed_data` row | FR-004, NFR-002 |
| LLM timeout / rate limit | SDK retries, then error surfaced | no partial `cv_version` written | NFR-002 |
| LLM refusal (`stop_reason: refusal`) | checked explicitly before reading content | treated as a generation failure with a distinct `error_type` | NFR-003 |
| Grounding rejects claims | grounding report | bullets dropped/flagged, run recorded as `rejected_claims` | G3 (zero fabrication) |
| PDF render failure | logged | `cv_version` intact, export retryable | NFR-002 |
| DB unavailable | request fails 503 | capture client retries; nothing half-written | atomicity |
| Disk full (storage) | export fails | DB rows intact | NFR-002 |

## 8. Future ATS Adapter Boundary

`adapters/` at repo root (distinct from `apps/api/src/oscar_api/adapters/`) is reserved for **site automation** adapters (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, generic) at P3. Nothing is implemented in V1. The boundary is declared now so that when it arrives it depends on `applications` and `career` through their service APIs — site-specific code must never become core domain logic (Decision Rule 15). The same rule already applies to site-specific *capture* extractors ([08_BROWSER_EXTENSION_DESIGN](08_BROWSER_EXTENSION_DESIGN.md)).

## 9. Technology Choices and Trade-offs

| Choice | Rationale | Trade-off accepted | Revisit when |
|---|---|---|---|
| FastAPI + Pydantic | Fixed by spec §8; typed, async, free OpenAPI for the extension/web clients | — | never (fixed) |
| PostgreSQL 16 | Fixed by spec §8; needs real transactions + `JSONB` + array columns for tags | Heavier local setup than SQLite | never (fixed) |
| SvelteKit + TS + Tailwind | Fixed by spec §8/§25 | Smaller ecosystem than React | never (fixed) |
| Modular monolith | Matches single-user scale; spec §32 | Would need work to become multi-tenant | if the product ever serves others |
| `BackgroundTasks`, no queue | Spec §27; a handful of tasks/day | Task lost on restart; no retry history | CV gen p95 > 60 s |
| Local filesystem for PDFs | Simplest; data stays on-device | Breaks on ephemeral hosting | if OPEN-1 resolves to option D |
| OpenAI `gpt-4.1` default (ADR-025) | Strong structured-output reliability; provider behind `LLMProvider` port | Not the cheapest tier available (mini/nano exist) | see cost model in [06_AI_LLM_DESIGN](06_AI_LLM_DESIGN.md) |
| npm (not pnpm) | pnpm not installed on this machine | Slower installs | anytime; no lock-in |
| Deterministic fact retrieval (no vector DB) | Explainable, no extra infra, small corpus | Misses semantic matches keyword scoring won't catch | if recall proves inadequate in evals |
