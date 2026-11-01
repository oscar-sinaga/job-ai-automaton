# 13 — Observability

NFR-003 requires that every important workflow emits component, action, result, latency, error type, version, and relevant IDs. Master spec §22 additionally wants failure telemetry good enough to drive the *improvement loop* — production failure → cluster → issue → patch → regression test.

For a single-user local tool, that means: structured JSON to stdout and a rotating file, queryable with `jq`. No Datadog, no OpenTelemetry collector, no dashboards.

---

## 1. Two Kinds of Events — Do Not Conflate

| | Domain events | Operational telemetry |
|---|---|---|
| Examples | `JOB_SAVED`, `CV_APPROVED`, `INTERVIEW_RECEIVED` | `cv_generation` succeeded in 18.4 s; parser raised `TIMEOUT` |
| Stored in | Postgres `job_events` / `application_events` | log files |
| Lifetime | forever (audit + analytics) | rotated, ~30 days |
| Consumer | the user, via UI and analytics | the developer, when something breaks |
| Rule | append-only, never deleted | freely discardable |

Keeping these separate matters: putting telemetry in the event tables would pollute analytics (a retried parse is not a user action), and putting domain events only in logs would destroy the funnel. Everything in [10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) reads the former; everything in this document is the latter.

## 2. Log Record Schema

Every operational log line is one JSON object with a fixed core:

```json
{ "ts": "2026-08-28T09:15:03.412+07:00",
  "level": "INFO",
  "component": "cv_generator",
  "action": "generate",
  "result": "success",
  "latency_ms": 18412,
  "job_id": 42,
  "cv_version_id": 88,
  "model_name": "gpt-4.1",
  "prompt_version": "cv_generator/v1",
  "app_version": "0.4.1",
  "request_id": "resp_018EeWyXxfu5pfWkrYcMdjWG",
  "trace_id": "9f2c1a7e",
  "input_tokens": 6480, "output_tokens": 2310, "cache_read_tokens": 4500,
  "claims_checked": 14, "claims_rejected": 1 }
```

| Field | Always present | Notes |
|---|---|---|
| `component` | ✓ | `capture`, `job_parser`, `cv_generator`, `grounding`, `pdf_export`, `applications`, `analytics`, `api` |
| `action` | ✓ | verb within the component |
| `result` | ✓ | `success` \| `failure` \| `partial` |
| `latency_ms` | ✓ for any timed operation | |
| `error_type` | on failure | from the closed set in §4 |
| `app_version` | ✓ | git describe / package version — a failure must be attributable to a build |
| `trace_id` | ✓ | per-request ID, propagated into background tasks so a capture and its later parse are correlatable |
| `request_id` | LLM calls | OpenAI's `response.id`, for provider support tickets |
| `*_version` | LLM calls | `model_name`, `prompt_version`, `parser_version` |

`trace_id` propagating into `BackgroundTasks` is the detail that makes in-process background work debuggable — without it, an async parse failure has no link back to the capture that triggered it.

## 3. Redaction Is Structural

Content never enters logs — only IDs, lengths, and counts. Enforced by a logging filter, with a unit test ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §5, [12_TEST_STRATEGY](12_TEST_STRATEGY.md) §3), not by reviewer discipline:

| Instead of | Log |
|---|---|
| raw JD text | `snapshot_id`, `raw_text_length` |
| CV bullet text | `cv_version_id`, `claims_checked`, `claims_rejected`, rejection *reasons* (not the rejected text) |
| career fact statements | `fact_ids: ["ach_41","ach_44"]` |
| the URL with query string | scheme + host + path |

The design test: a failed CV generation must be fully diagnosable from its log line plus a database lookup. If a log line needs to quote a bullet to be useful, the schema is wrong.

## 4. Failure Classification

A closed `error_type` set — the same one the API returns ([05_API_DESIGN](05_API_DESIGN.md) §1) — so failures can be counted and clustered by grepping, without parsing prose:

```text
capture:      INVALID_ENVELOPE · DUPLICATE_IDEMPOTENCY_KEY · DB_UNAVAILABLE · PAYLOAD_TOO_LARGE
job_parser:   LLM_TIMEOUT · LLM_REFUSED · SCHEMA_INVALID · EMPTY_INPUT · UNEXPECTED
cv_generator: LLM_TIMEOUT · LLM_REFUSED · LLM_UNAVAILABLE · SCHEMA_INVALID · NO_FACTS_RETRIEVED
grounding:    NO_SUPPORTING_FACT · FACT_NOT_RETRIEVED · UNVERIFIED_METRIC · METRIC_MISMATCH
              UNKNOWN_TECHNOLOGY · UNKNOWN_EMPLOYER · DATE_INCONSISTENT · SEMANTIC_DRIFT
pdf_export:   TEMPLATE_ERROR · STORAGE_ERROR · FONT_MISSING
applications: ILLEGAL_TRANSITION · CONFLICT
```

The `grounding:` values are shared with `cv_generation_runs.grounding_report.rejections[].reason` ([04_DATA_MODEL](04_DATA_MODEL.md) §5), so the same taxonomy appears in the user-facing report, the logs, and the eval results. One vocabulary, three consumers.

Master spec §22's example maps directly onto this schema:

```json
{ "component": "greenhouse_adapter", "app_version": "2.3.1",
  "action": "resume_upload", "result": "failure",
  "error_type": "ELEMENT_NOT_FOUND", "job_id": 42 }
```

That shape is why `component` + `action` + `error_type` + `app_version` are mandatory: they are exactly the fields a future adapter-failure cluster needs, and adding them later would mean re-instrumenting everything.

## 5. Where Logs Go

```text
stdout                          → developer console during `uvicorn` runs
var/logs/oscar-api.jsonl        → rotating file (10 MB × 5), git-ignored
```

Useful queries, which is the whole point of JSON lines:

```bash
# all failures in the last run, grouped by type
jq -r 'select(.result=="failure") | .error_type' var/logs/oscar-api.jsonl | sort | uniq -c | sort -rn

# CV generation latency distribution
jq -r 'select(.component=="cv_generator" and .action=="generate") | .latency_ms' var/logs/oscar-api.jsonl

# grounding rejection reasons over time — is a prompt change making things worse?
jq -r 'select(.component=="grounding") | "\(.ts[0:10]) \(.error_type)"' var/logs/oscar-api.jsonl | sort | uniq -c

# is prompt caching actually working? (should be non-zero after the first call of a session)
jq -r 'select(.component=="cv_generator") | .cache_read_tokens' var/logs/oscar-api.jsonl
```

The last query is a concrete example of telemetry earning its cost: the cache-invalidation pitfalls in [06_AI_LLM_DESIGN](06_AI_LLM_DESIGN.md) §5 are silent — the only way to know caching broke is to look at `cache_read_tokens`.

## 6. Metrics Worth Watching During Stabilization

Not a monitoring system — a short list to check weekly in Milestone 6:

| Signal | Healthy | Action if not |
|---|---|---|
| capture failure rate | ~0% | investigate immediately; capture is P0 and its failures are user-visible |
| parse failure rate | < 20% | tolerable by design; feeds P1 parser work |
| CV generation p95 latency | < 60 s | lower `effort`, or move to a durable queue (OPEN-3) |
| grounding rejection rate | stable | a *rise* after a prompt change means regression — re-run evals |
| `cache_read_tokens` on 2nd+ generation of a session | > 0 | a silent cache invalidator has been introduced |
| unclassified `UNEXPECTED` errors | 0 | each one is a missing entry in the taxonomy above |

## 7. Explicitly Not Built

No tracing backend, no metrics store (Prometheus/Grafana), no error aggregator (Sentry), no alerting, no uptime monitoring. All are disproportionate for one user on one machine, and stdout + `jq` covers the actual need: figuring out why something failed after it failed. Revisit only if the app becomes hosted (OPEN-1 option D).
