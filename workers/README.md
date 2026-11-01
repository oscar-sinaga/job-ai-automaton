# workers/ — Background processing (not implemented)

V1 has **no separate worker process**. Parsing, CV generation, and PDF rendering run as FastAPI `BackgroundTasks` inside the API process (ADR-004, master spec §27).

Rationale: a handful of short, idempotent, UI-retryable tasks per day does not justify Redis + a queue library + a second process to supervise.

## Accepted limitation

Tasks are lost if the server restarts mid-flight, and there is no retry history. Acceptable because every task is re-runnable from the UI (`POST /jobs/{id}/parse`, `POST /jobs/{id}/generate-cv`).

## Revisit trigger (OPEN-3)

This directory becomes real if either:

- CV generation p95 latency exceeds 60 s, or
- lost-on-restart tasks become a genuine annoyance during Milestone 6.

Both are observable from the signals in [../docs/13_OBSERVABILITY.md](../docs/13_OBSERVABILITY.md) §6 — so the decision will be made from data, not preference.
