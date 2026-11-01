# 05 — API Design

Base path `/api/v1`. Milestone 0 ships only `GET /health`; everything else here is the contract for M1–M5.

---

## 1. Conventions

| Concern | Decision |
|---|---|
| Auth | `X-API-Key: <OSCAR_API_KEY>` on every request except `/health`; compared with `secrets.compare_digest` |
| Content type | `application/json`; UTF-8 |
| Timestamps | ISO 8601 with offset, e.g. `2026-08-28T09:15:00+07:00`; stored as UTC |
| IDs | integers in JSON; `jobs` additionally expose `ref` (`"J001"`) for display |
| Pagination | `?limit=` (default 50, max 200) + `?cursor=`; response carries `next_cursor` (null at the end) |
| Errors | uniform envelope (below); FastAPI's 422 body is left as-is for schema validation failures |
| Idempotency | `Idempotency-Key` header honoured on `POST /jobs/capture` |
| Events | any endpoint that changes status writes exactly one event in the same transaction |

### Error envelope

```json
{ "error_type": "ILLEGAL_TRANSITION",
  "message": "Cannot move job J001 from REJECTED to INTERVIEW",
  "detail": { "from": "REJECTED", "to": "INTERVIEW" } }
```

| `error_type` | HTTP | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing/incorrect API key |
| `NOT_FOUND` | 404 | Unknown entity |
| `ILLEGAL_TRANSITION` | 409 | Status change not permitted by the state machine ([04_DATA_MODEL](04_DATA_MODEL.md) §6) |
| `CONFLICT` | 409 | e.g. marking a second CV version as submitted |
| `LLM_UNAVAILABLE` | 503 | Provider error/timeout after retries |
| `LLM_REFUSED` | 422 | `stop_reason: refusal` from the model |
| `GROUNDING_FAILED` | 422 | Every candidate bullet was rejected; no version persisted |
| `STORAGE_ERROR` | 503 | PDF write failed |
| `INTERNAL` | 500 | Unclassified |

Error types are a closed set so [13_OBSERVABILITY](13_OBSERVABILITY.md) can cluster failures without parsing prose.

---

## 2. Health (Milestone 0)

```http
GET /health  →  200
{ "status": "ok", "version": "0.1.0", "db": "ok" }
```

`db` is `"ok"` / `"unavailable"` from a `SELECT 1`. It never returns non-200 on DB failure — the endpoint's job is to report state, and a liveness probe that fails because a dependency is down makes diagnosis harder, not easier.

---

## 3. Capture

```http
POST /api/v1/jobs/capture
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7

{ "url": "https://www.linkedin.com/jobs/view/4012345678/",
  "source_hint": "linkedin.com",
  "page_title": "Machine Learning Engineer - Acme",
  "raw_text": "About the job\nWe are looking for...",
  "selected_text": null,
  "shared_text": null,
  "captured_at": "2026-08-28T09:15:00+07:00",
  "capture_method": "extension",
  "metadata": { "extension_version": "0.1.0" } }
```

```json
201
{ "job_id": 42, "ref": "J042",
  "capture_completeness": "CAPTURED_COMPLETE",
  "duplicate_of_job_id": null,
  "snapshot_id": 57 }
```

Rules:
- `url` and `captured_at` are the only required fields. Everything else may be absent — a URL-only mobile share is a valid request.
- `capture_completeness` is **derived server-side**, never trusted from the client: JD text present → `CAPTURED_COMPLETE`; only URL/title → `CAPTURED_PARTIAL`; `manual_url` with no text → `NEEDS_ENRICHMENT`.
- Repeating the same `Idempotency-Key` returns `200` with the original `job_id` (no new row).
- `raw_text` is capped at 200 KB; longer bodies are truncated with `metadata.truncated = true` recorded on the snapshot rather than rejected.
- Returns before parsing starts. Parsing is a background task and its outcome never affects this response.

### Enrichment (turning a partial capture complete)

```http
POST /api/v1/jobs/{id}/snapshots
{ "raw_text": "...full JD pasted from desktop...",
  "capture_method": "paste_text",
  "captured_at": "2026-08-28T20:02:00+07:00" }
→ 201 { "snapshot_id": 58, "capture_completeness": "CAPTURED_COMPLETE" }
```

Adds a snapshot; never mutates the existing one (FR-003).

---

## 4. Jobs

```http
GET /api/v1/jobs?status=SAVED&source=linkedin&q=engineer&limit=50&cursor=...
→ 200 { "items": [ { "id": 42, "ref": "J042", "title": "...", "company": "Acme",
                     "source": "linkedin", "current_status": "SAVED",
                     "capture_completeness": "CAPTURED_COMPLETE",
                     "cv_ready": true, "latest_cv_version": 2,
                     "created_at": "...", "is_duplicate": false } ],
        "next_cursor": "eyJpZCI6NDJ9" }

GET   /api/v1/jobs/{id}          → job + latest parsed data + snapshots (metadata only, not full text)
                                   + cv_versions summary + timeline (job_events + application_events merged)
GET   /api/v1/jobs/{id}/raw      → { "snapshot_id": 57, "raw_text": "..." }   (separate call: bodies are large)
PATCH /api/v1/jobs/{id}          → manual field corrections; writes JOB_PARSE_CORRECTED when parsed fields change
POST  /api/v1/jobs/{id}/parse    → 202 { "task": "queued" }
POST  /api/v1/jobs/{id}/status   → { "status": "SKIPPED" }  (pre-application transitions only)
```

`cv_ready` is computed (a `CV_APPROVED` event exists) rather than stored, so the inbox and the dashboard backlog can never disagree about it.

---

## 5. CV

```http
POST /api/v1/jobs/{id}/generate-cv
{ "preferences": { "max_bullets_per_role": 4, "include_projects": true },
  "regenerate_section": null }
→ 201
{ "cv_version_id": 88, "label": "CV_J042_v1",
  "sections": { ... },                     // shape in doc 04 §5
  "missing_requirements": ["Kubernetes (not in profile)"],
  "grounding_report": {
    "claims_checked": 14, "claims_rejected": 1,
    "rejections": [ { "text": "Led a team of 8 engineers.",
                      "reason": "NO_SUPPORTING_FACT" } ] },
  "run": { "model_name": "gpt-4.1", "prompt_version": "cv_generator/v1",
           "input_tokens": 6480, "output_tokens": 2310, "latency_ms": 18400 } }
```

`regenerate_section` (e.g. `"summary"`, `"experience.7"`) regenerates one section and produces a new version, writing `CV_REGENERATED`.

```http
GET   /api/v1/jobs/{id}/cv-versions      → list (id, version_number, is_submitted, created_at)
GET   /api/v1/cv/{id}                    → full version incl. per-bullet supporting_fact_ids
PATCH /api/v1/cv/{id}                    → { "sections": {...} } → creates a NEW version, writes CV_EDITED
POST  /api/v1/cv/{id}/approve            → writes CV_APPROVED, job → READY_TO_APPLY
POST  /api/v1/cv/{id}/export             → 201 { "artifact_id": 12, "storage_uri": "...", "download_url": "..." }
POST  /api/v1/cv/{id}/mark-submitted     → unsets any prior submitted version for the job (one txn), 409 on conflict
```

`PATCH /cv/{id}` creating a new version rather than mutating is the mechanism behind US-4: a CV that was submitted must remain byte-stable forever.

---

## 6. Applications

```http
POST /api/v1/applications
{ "job_id": 42, "submitted_cv_version_id": 88 }
→ 201 { "application_id": 15, "current_status": "APPLIED" }
      # writes APPLICATION_SUBMITTED + marks cv_version submitted, one transaction

POST /api/v1/applications/{id}/events
{ "event_type": "INTERVIEW_RECEIVED", "occurred_at": "2026-09-03T10:00:00+07:00",
  "metadata": { "round": 1, "format": "technical" } }
→ 200 { "event_id": 301, "current_status": "INTERVIEW" }
→ 409 ILLEGAL_TRANSITION if the state machine forbids it

GET   /api/v1/applications/{id}          → application + submitted CV ref + full event history
PATCH /api/v1/applications/{id}          → non-status fields only
POST  /api/v1/applications/{id}/answers  → { "question_key": "notice_period", "answer_text": "1 month", "is_private": false }
```

`occurred_at` is client-supplied and optional (defaults to now) because status updates are often entered after the fact — "I interviewed on Tuesday" must be recordable on Thursday without distorting the funnel timeline.

---

## 7. Career Profile

```http
GET   /api/v1/career-profile         → profile + all nested entities (single payload; it is small and always read whole)
PATCH /api/v1/career-profile         → summary and profile-level fields

POST|PATCH|DELETE /api/v1/career-profile/experiences[/{id}]
POST|PATCH|DELETE /api/v1/career-profile/projects[/{id}]
POST|PATCH|DELETE /api/v1/career-profile/skills[/{id}]
POST|PATCH|DELETE /api/v1/career-profile/education[/{id}]
POST|PATCH|DELETE /api/v1/career-profile/certifications[/{id}]
POST|PATCH|DELETE /api/v1/career-profile/achievements[/{id}]
GET|PATCH        /api/v1/career-profile/application-profile
```

All six nested collections share one CRUD shape: `POST` to the collection, `PATCH`/`DELETE` on the item, item bodies matching the columns in [04_DATA_MODEL](04_DATA_MODEL.md) §3. `DELETE` on an achievement is a soft delete — CV versions that cite it must remain explainable.

---

## 8. Dashboard & Analytics

```http
GET /api/v1/dashboard?window=30d
→ 200
{ "kpis": { "saved": 52, "ready_to_apply": 9, "applied": 27, "assessment": 4,
            "interview": 6, "final_interview": 2, "offer": 1, "rejected": 11 },
  "funnel": [ {"stage":"SAVED","count":52}, {"stage":"APPLIED","count":27},
              {"stage":"ASSESSMENT","count":4}, {"stage":"INTERVIEW","count":6},
              {"stage":"FINAL_INTERVIEW","count":2}, {"stage":"OFFER","count":1} ],
  "conversion": { "applied_over_saved": 0.519, "assessment_over_applied": 0.148,
                  "interview_over_applied": 0.222, "offer_over_interview": 0.167,
                  "offer_over_applied": 0.037 },
  "backlog": { "cv_ready_not_applied": 9, "saved_older_than_5d": 5,
               "jobs_without_cv": 16, "applications_needing_action": 2 },
  "action_queue": [ { "label": "CV ready but not applied", "count": 9,
                      "href": "/jobs?status=READY_TO_APPLY" },
                    { "label": "Saved more than 5 days ago", "count": 5,
                      "href": "/jobs?status=SAVED&older_than=5d" } ],
  "sample_note": "Analytics describe your captured-job sample, not the job market." }

GET /api/v1/analytics/funnel?window=90d
GET /api/v1/analytics/trends?granularity=week&window=90d
GET /api/v1/analytics/sources
GET /api/v1/analytics/roles
GET /api/v1/analytics/skills?top=20
GET /api/v1/analytics/productivity
```

Every `action_queue` item carries the `href` that reproduces exactly the set it counted — that is what makes the dashboard actionable (FR-011) instead of decorative. Formulas for every number above live in [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) and are implemented in one place (`modules/analytics/queries.py`) so the dashboard and the analytics endpoints cannot drift apart.

---

## 9. Versioning

`/api/v1` from the start. The only consumers are the SvelteKit app and the extension, both versioned together with the API, so breaking changes are cheap today — but the extension can lag (users delay updates), which is the reason the prefix exists at all. Breaking changes get `/api/v2`; `v1` is not mutated in place.
