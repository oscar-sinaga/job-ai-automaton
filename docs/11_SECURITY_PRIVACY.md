# 11 — Security & Privacy

The data here is a complete professional dossier on one person: employment history, achievements, contact details, salary expectations, and every job they were interested in but did not get. Master spec §41 rates *sensitive data leakage* as **critical**.

This is a single-user, local-first application, so the threat model is not "attacker on the internet" by default — it is disclosure through carelessness: a secret in git, PII in logs, a public tunnel, an unencrypted backup, or an unnoticed third-party disclosure.

---

## 1. Data Inventory and Sensitivity

| Data | Sensitivity | Where it lives |
|---|---|---|
| Career facts (employers, dates, achievements) | High — professional identity | Postgres `career_*` |
| Contact details, links | High — direct PII | Postgres `application_profiles` |
| Salary expectation, current salary | **Highest** — leverage-sensitive | Postgres `application_profiles`, `application_answers` |
| Raw job descriptions | Low-medium — third-party content | Postgres `job_raw_snapshots` |
| Application history and outcomes (rejections) | High — reputationally sensitive | Postgres `applications`, `*_events` |
| Generated CV PDFs | High — PII in a portable file | `var/storage/` |
| `OSCAR_API_KEY`, `OPENAI_API_KEY` | Highest — credentials | `.env` only |
| Application answers marked private | Highest by user declaration | `application_answers.is_private` |

## 2. Secrets Handling

- All secrets come from environment variables, loaded via `pydantic-settings` from `.env`. No secret is ever a literal in code, a default value, or a test fixture.
- `.env` is git-ignored; `.env.example` contains only placeholder values and is the documented source of truth for *which* variables exist.
- No plaintext credentials for job sites are stored — **ever**. The product never asks for LinkedIn/JobStreet passwords, and no V1 feature requires them (user-plan §18, master spec NFR-004). This is a design boundary, not a current limitation: the P3 ATS work must also not introduce credential storage without a separate security review.
- CI runs a secret scan (`gitleaks`) on every push; a hit fails the build.
- If a secret is ever committed, rotation is the fix, not a revert — history is assumed compromised.

## 3. Authentication and Network Exposure

| Surface | Control |
|---|---|
| API | `X-API-Key` on every route except `/health`, compared with `secrets.compare_digest` (constant-time; a naive `==` leaks key material through timing) |
| Postgres | bound to `127.0.0.1` only in `docker-compose.yml`; never `0.0.0.0` |
| CORS | explicit allowlist (web dev origin + extension origin). No `allow_origins=["*"]`, which would let any visited website POST to the local API |
| Extension | `activeTab` only; API key in `chrome.storage.local`; never injected into pages ([08_BROWSER_EXTENSION_DESIGN](08_BROWSER_EXTENSION_DESIGN.md) §5) |
| Mobile reachability | Tailscale (private mesh) is the recommended option precisely because it avoids public exposure — see [09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §2 |

**If OPEN-1 resolves to a public tunnel (option C) or hosted VPS (option D), this section must be revised before that ships**: a public origin turns a single static API key from "adequate LAN guard" into "the only thing between the internet and a complete personal dossier". Minimum additions in that case: TLS, rate limiting, per-client keys, and access logging.

## 4. Third-Party Disclosure to the LLM Provider

The one deliberate off-device flow. Recorded here explicitly so it is a decision, not a surprise.

**Sent to OpenAI** (ADR-025) on each CV generation: selected career facts (employers, titles, dates, achievement statements, verified metrics) and the raw job description.

**Never sent:** contact details, phone, address, salary expectation or current salary, national ID, any `application_answers` row, and any answer marked `is_private`. The prompt builder receives a filtered projection of the career profile — the filter is code (`career/projections.py`), and a test asserts that the projection contains none of the excluded fields, so this cannot regress silently as the schema grows.

Additional controls:
- API key scoped to this application; usage visible in the OpenAI platform dashboard.
- Data-retention posture of the provider account is the owner's decision to review (zero-data-retention options exist for some configurations); the choice is recorded in [17_DECISION_LOG](17_DECISION_LOG.md).
- The user can generate CVs from a reduced fact set if a particular job feels sensitive — retrieval is deterministic and inspectable, so what was sent is always knowable after the fact via `cv_generation_runs`.

## 5. Log Redaction (NFR-003 + NFR-004)

Observability must not become a second, unprotected copy of the database. Rules enforced by a logging filter, not by convention:

| Never logged | Logged instead |
|---|---|
| Raw JD text | `snapshot_id`, `raw_text_length` |
| CV bullet text | `cv_version_id`, `claims_checked`, `claims_rejected` |
| Career fact statements | `fact_id` list |
| Contact details, salary figures | nothing |
| API keys, auth headers | nothing (header allowlist on request logs) |
| Full URLs with query strings | scheme + host + path, query dropped (tracking params can carry identifiers) |

The rule of thumb: **logs carry IDs and shapes, never content.** A failed CV generation must be diagnosable from `job_id`, `prompt_version`, `model_name`, `error_type`, and rejection reasons alone — see [13_OBSERVABILITY](13_OBSERVABILITY.md).

## 6. Generated CV Files

- Stored under `var/storage/`, git-ignored, outside any directory the web server serves statically.
- Downloads go through the API (`GET /api/v1/cv/{id}/download`) with the same auth as everything else, so a PDF is never reachable by guessing a path.
- Filenames use the job ref and version (`J042_v2.pdf`), not the person's name — a downloaded file shouldn't broadcast whose CV it is from its filename alone.
- Deleting a CV version deletes its artifacts.

## 7. Export and Delete (user-plan §18, NFR-004)

| Capability | Implementation |
|---|---|
| Full export | `GET /api/v1/export` → single JSON with every table's rows plus a manifest; CV PDFs zipped alongside |
| Delete a job | Cascades to snapshots, parsed data, CV versions, artifacts, events, application |
| Delete everything | Documented `make reset` (drops schema, clears `var/storage/`) — destructive, interactive confirmation required |
| Soft delete | Career facts only, so CV versions citing them remain explainable ([05_API_DESIGN](05_API_DESIGN.md) §7) |

Export exists for portability *and* as the backup mechanism — see [14_DEPLOYMENT_PLAN](14_DEPLOYMENT_PLAN.md) §Backups. An irreplaceable hand-curated fact store with no backup is a data-loss risk equal to any security risk in this document.

## 8. Audit Trail

The append-only event tables ([04_DATA_MODEL](04_DATA_MODEL.md) §6) double as the audit log for user-facing actions: what was generated, approved, exported, submitted, and when. Because they are never updated or deleted, they answer "which CV did I actually send to this company" even years later — which is both a product feature (US-4) and the accountability record if a claim in a submitted CV is ever questioned.

## 9. Non-Goals (V1)

No multi-user RBAC · no at-rest encryption beyond OS-level disk encryption · no SSO · no audit log shipping · no intrusion detection · no secrets manager (`.env` is sufficient for a single local user). Each is disproportionate to a single-user local tool, and each becomes required if OPEN-1 resolves toward hosting the application publicly.
