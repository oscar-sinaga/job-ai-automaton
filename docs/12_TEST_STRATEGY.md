# 12 — Test Strategy

Testing priorities follow the product's actual risks, not code coverage as an abstract goal. In order: **(1) grounding correctness, (2) no data loss, (3) analytics correctness, (4) everything else.**

Milestone 0 ships one test (`/health`) plus the harness and CI wiring. The rest arrives with the features it covers.

---

## 1. What Must Never Break

| Invariant | Guarded by |
|---|---|
| A generated CV contains no unsupported claim | Grounding unit tests + adversarial eval set (§5) |
| A captured job is never lost, whatever else fails | Fault-injection integration tests (§4) |
| A raw snapshot is never modified | Append-only test + DB-level assertion |
| An illegal status transition is impossible | State-machine table-driven tests |
| A submitted CV version stays byte-identical | Immutability test on edit-creates-new-version |
| Dashboard numbers match reality | Hand-counted fixture dataset (§6) |

Every one of these maps to a [01_PRD](01_PRD.md) goal (G3, G4, G5) rather than to a module.

## 2. Tooling

| Concern | Choice |
|---|---|
| Runner | `pytest` (+ `pytest-asyncio`) for the API, `vitest` for web/extension |
| HTTP tests | `httpx.AsyncClient` against the FastAPI app via ASGI transport (no live server needed) |
| Database | Real PostgreSQL from `docker-compose`; **never SQLite** — the schema uses enums, `text[]`, GIN and partial indexes that SQLite cannot represent, so a SQLite test suite would validate a different schema than production |
| Test isolation | Each test runs in a transaction that is rolled back; schema created once per session via `alembic upgrade head` |
| LLM | `FakeLLMProvider` injected through the `LLMProvider` port. **No test calls a real model** — LLM tests would be slow, non-deterministic, and paid |
| Lint / format / types | `ruff` (lint + format), `mypy` on `modules/` and `ports/`; `svelte-check` for web |
| Import boundaries | `import-linter` contract enforcing the dependency rules in [03_SYSTEM_ARCHITECTURE](03_SYSTEM_ARCHITECTURE.md) §2 |

## 3. Unit Tests

Highest-value targets, roughly in priority order:

- **Grounding verification (V1–V6)** — the largest and most valuable unit-test suite in the project. Each rule gets passing cases, rejecting cases, and boundary cases (a number that appears in the *fact context* but not the metric; a technology mentioned only in the JD; an employer named in a project description).
- **Status state machine** — table-driven over all 11 statuses × all event types: every legal transition succeeds, every illegal one raises. Generated from the same table that the implementation reads, so the two cannot drift.
- **Analytics formulas** — each metric against small in-memory-built fixtures where the answer is hand-derivable.
- **URL canonicalisation and dedupe keys** — tracking-param stripping, source-job-ID extraction per site, the company+title fallback.
- **Capture-completeness derivation** — the server-side rule, including the "client claims complete but sent no text" case.
- **Event creation** — every status-changing service call writes exactly one event, with the right actor and metadata.
- **Text extraction heuristic** (extension, `vitest`) — against saved HTML fixtures.
- **Log redaction filter** — asserts that JD text, bullet text, and API keys never survive into formatted output ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §5).
- **Career projection filter** — asserts the LLM-bound projection contains no contact details, salary, or private answers ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §4).

## 4. Integration Tests

Each covers a vertical slice end-to-end through the real API and real database:

| Test | Asserts |
|---|---|
| Capture (all four methods) | job + snapshot + `JOB_SAVED` event in one transaction; correct completeness derived |
| Capture idempotency | same `Idempotency-Key` twice → one job, second response 200 |
| Capture duplicate | same dedupe key → two jobs, second flagged `duplicate_of_job_id` |
| Enrichment | second snapshot added; **first snapshot byte-identical**; completeness upgraded |
| Career profile → CV generation | uses `FakeLLMProvider`; produces a version with provenance and a grounding report |
| Grounding rejection path | fake provider returns a fabricated bullet → bullet dropped, run status `rejected_claims`, no fabrication persisted |
| All-rejected path | `422 GROUNDING_FAILED`, **no `cv_version` row created** |
| CV edit | creates a new version; the prior version is unchanged |
| Application flow | submit → assessment → interview ×2 → offer, with correct materialised status and event trail |
| Illegal transition | `REJECTED → INTERVIEW` → `409 ILLEGAL_TRANSITION`, no event written |
| PDF export | artifact row + file on disk; failure leaves the CV version intact |
| Dashboard query | numbers match the hand-counted fixture (§6) |
| Backlog links | each action-queue `count` equals the length of the list its `href` returns |

### Fault injection (guards G4 / NFR-002)

Three tests that matter more than their line count suggests, because they encode the product's core reliability promise:

1. Parser raises → capture still 201; job and raw text intact; no `job_parsed_data` row.
2. LLM times out / refuses → job, raw text, and prior CV versions intact; no partial version written.
3. Storage write fails → `cv_version` intact; export retryable.

## 5. Evals (LLM quality — separate from tests)

Evals are **not** part of the CI test suite: they cost money and are non-deterministic. They run on demand and are gated on prompt/model changes ([07_CV_GROUNDING_AND_EVALS](07_CV_GROUNDING_AND_EVALS.md) §8).

```bash
uv run python scripts/eval_cv_grounding.py --case ../../evals/cv_grounding/cases/001_mlops_engineer
```

| Suite | Measures | Gate |
|---|---|---|
| `cv_grounding` | fabrication rate, verifier recall/precision, fact recall | fabrication rate 0 and verifier recall 100% required to adopt a change |
| `job_extraction` | field-level accuracy vs. hand-labelled fixtures | tracked, not gating (parser is P1, non-blocking by design) |
| `skill_extraction` | precision/recall on required vs. preferred skills | tracked |
| `requirement_classification` | must-have vs. nice-to-have | tracked |

Results are written to `evals/results/<date>_<model>_<prompt>.json` so quality across model and prompt versions is comparable over time rather than anecdotal.

## 6. Fixtures

```text
fixtures/
  jobs/
    linkedin_ml_engineer.txt          jobstreet_data_scientist.txt
    glints_backend.txt                dealls_ai_engineer.txt
    kalibrr_analyst.txt               company_career_page.html
    malformed_no_jd.html              very_short_jd.txt
    duplicate_pair_a.txt              duplicate_pair_b.txt
  profiles/
    oscar_sanitised.json              minimal_profile.json
  analytics/
    funnel_dataset.sql                # + expected_values.json
```

All job fixtures are **sanitised** real-world text (company names replaced, no personal data), covering the sources named in master spec §28.

The analytics dataset deliberately includes the cases that break naive implementations: a skipped job, a withdrawn application, a duplicate pair, a job that reached interview then was rejected, a three-round interview, and a job that skipped assessment entirely. `expected_values.json` holds hand-counted answers for every formula in [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) — computed by hand, not by running the code, or the test proves nothing.

## 7. CI Pipeline

```text
push / PR
  ├── secret scan (gitleaks)
  ├── api:  uv sync → ruff check → ruff format --check → mypy → alembic upgrade/downgrade → pytest
  ├── web:  npm ci → svelte-check → npm run build
  └── (extension, once it exists): npm ci → vitest → build
```

Migrations are exercised **both directions** (`upgrade head` then `downgrade -1`) against a real Postgres service container, because an untested `downgrade` is a rollback that will fail exactly when it is needed most.

Evals are excluded from CI (cost, non-determinism) and run manually before adopting a prompt or model change.

## 8. What Is Deliberately Not Tested in V1

- Browser end-to-end (Playwright) — the UI is intentionally simple and changes fast; integration tests at the API boundary catch the failures that matter.
- Load/performance testing — one user.
- Cross-browser matrix — Chrome/Edge only.
- Visual regression — there is no design system to regress ([01_PRD](01_PRD.md) §6 non-goals).

These are noted as conscious omissions so their absence is not later mistaken for oversight.
