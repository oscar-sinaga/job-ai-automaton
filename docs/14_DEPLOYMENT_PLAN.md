# 14 — Deployment Plan

V1 target: **run locally on Oscar's Windows laptop.** Nothing is deployed to a cloud provider unless OPEN-1 forces it ([09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §2). Milestone 0 delivers exactly the setup described in §1–§3.

Update 2026-11-10: workspace CV preferences, export/delete and integration settings
are implemented. See [Settings behavior and rollout](SETTINGS.md). Tencent hosting
is an explicit operator deployment; the historical local-first topology below
remains useful for development.

Update 2026-11-02: the complete local Compose runtime, isolated simulation mode,
persistent volumes and backup/restore verification are documented in
[20_MVP_PILOT.md](20_MVP_PILOT.md). The development-server instructions below
remain available for editing source code.

---

## 1. Local Topology

```text
Windows 11 laptop
├── Docker Desktop
│     └── postgres:16          127.0.0.1:5432   (volume: pgdata)
├── uv (Python 3.12)
│     └── uvicorn apps/api     127.0.0.1:8000   → /api/v1, /health, /docs
├── Node 24 / npm
│     └── vite dev apps/web    127.0.0.1:5173   → proxies /api → :8000
├── var/storage/               generated CV PDFs
└── var/logs/                  oscar-api.jsonl
```

Postgres binds to `127.0.0.1` only, never `0.0.0.0` ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §3).

Python 3.12 is pinned via `.python-version`; `uv` downloads and manages it, so the system's Python 3.10.9 is irrelevant and left untouched.

## 2. First-Run Setup

```bash
git clone <repo> && cd job-ai-automaton
cp .env.example .env            # then fill in OPENAI_API_KEY and OSCAR_API_KEY

docker compose up -d db         # Postgres
cd apps/api && uv sync          # creates .venv, installs from uv.lock
uv run alembic upgrade head     # schema (empty baseline at M0)
uv run uvicorn oscar_api.main:app --reload --port 8000

cd ../web && npm install && npm run dev    # http://127.0.0.1:5173
```

Verify: `curl http://127.0.0.1:8000/health` → `{"status":"ok","db":"ok",...}`.

`uv sync` installs from `uv.lock`, so the environment is reproducible rather than "whatever resolved today". The lock file is committed.

## 3. Environment Variables

Every variable, its purpose, and whether it is a secret. `.env.example` mirrors this table with placeholder values; `.env` is git-ignored.

| Variable | Secret | Default | Purpose |
|---|---|---|---|
| `OSCAR_ENV` | no | `local` | `local` \| `test`; gates debug behaviour |
| `OSCAR_DATABASE_URL` | yes (contains password) | `postgresql+psycopg://oscar:oscar@127.0.0.1:5432/oscar` | Postgres DSN |
| `OSCAR_API_KEY` | **yes** | — | Shared key for web/extension/mobile clients ([03_SYSTEM_ARCHITECTURE](03_SYSTEM_ARCHITECTURE.md) §4) |
| `OSCAR_CORS_ORIGINS` | no | `http://127.0.0.1:5173` | Comma-separated allowlist; extension origin added at M1 |
| `OSCAR_STORAGE_DIR` | no | `var/storage` | Generated PDFs |
| `OSCAR_LOG_DIR` | no | `var/logs` | JSONL logs |
| `OSCAR_TIMEZONE` | no | `Asia/Jakarta` | Analytics bucketing ([10_ANALYTICS_DEFINITIONS](10_ANALYTICS_DEFINITIONS.md) §7) |
| `OPENAI_API_KEY` | **yes** | — | LLM provider (M3+, ADR-025) |
| `OSCAR_LLM_MODEL` | no | `gpt-6-luna` | CV generation model; cost-conscious default (ADR-027) |
| `OSCAR_LLM_PARSER_MODEL` | no | `gpt-6-luna` | Reserved parser model; parsing remains P1 |
| `OSCAR_LLM_MAX_OUTPUT_TOKENS` | no | `4096` | Output cap; validated range 512–16000 |

None of these have secret defaults — a missing `OSCAR_API_KEY` or `OPENAI_API_KEY` fails startup loudly rather than falling back to something insecure.

## 4. Mobile Access (ADR-019)

Recommended: **Tailscale.** Install on laptop and phone, then bind uvicorn to the Tailscale interface and point the mobile client at the machine's Tailscale hostname.

```bash
uv run uvicorn oscar_api.main:app --host 0.0.0.0 --port 8000
# reachable at http://<machine>.<tailnet>.ts.net:8000 — private mesh only, not the public internet
```

`--host 0.0.0.0` binds all interfaces including LAN, so this step is what makes `OSCAR_API_KEY` load-bearing rather than decorative. Options and trade-offs: [09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §2; decided as ADR-019 in [17_DECISION_LOG](17_DECISION_LOG.md).

## 5. Backups — the most important operational task

The career fact store is **hand-curated over hours and irreplaceable**. Losing it is worse than any bug in this backlog, and no amount of code quality substitutes for a copy of the data.

```bash
# nightly (Windows Task Scheduler)
docker compose exec -T db pg_dump -U oscar oscar | gzip > backups/oscar_$(date +%F).sql.gz
robocopy var\storage backups\storage /MIR
```

- Retention: 14 daily + 8 weekly, in a directory that is **not** inside the git repo.
- Off-machine copy: at minimum a synced cloud folder or external drive; a backup that lives only on the failing disk is not a backup.
- **Restore is tested, not assumed** — quarterly: restore into a scratch database and confirm `GET /api/v1/career-profile` returns the full profile. An untested restore is a hope.
- `GET /api/v1/export` ([11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §7) is the portable, human-readable second line of defence, independent of Postgres version.

This section exists because master spec §41's risk table omits data loss entirely — a gap worth closing before it becomes an incident (RISK-13 in [16_RISK_REGISTER](16_RISK_REGISTER.md)).

## 6. CI

GitHub Actions on push/PR — build and test only, **no deploy step**, because there is no deploy target.

```text
secret scan (gitleaks)
api:  uv sync → ruff check → ruff format --check → mypy
      → postgres service container → alembic upgrade head → alembic downgrade -1 → pytest
web:  npm ci → svelte-check → npm run build
```

Evals are excluded (cost, non-determinism) and run manually — [12_TEST_STRATEGY](12_TEST_STRATEGY.md) §5.

## 7. Production Hosting — Deliberately Deferred

Not decided, and not needed for V1 (OPEN-1). If it becomes necessary, the shape would be: managed Postgres + a small container host + object storage instead of local filesystem, and **[11_SECURITY_PRIVACY](11_SECURITY_PRIVACY.md) §3 must be revised first** — a public origin makes a single static API key insufficient, and it moves the entire career dossier off Oscar's machine.

Two things in the current design are what keep that option cheap rather than a rewrite: the `Storage` port (filesystem → S3 is one adapter) and the fact that no code outside `adapters/` knows where files live.

## 8. Runbook

| Task | Command |
|---|---|
| Start everything | `docker compose up -d db` then the two dev servers (§2) |
| Apply migrations | `cd apps/api && uv run alembic upgrade head` |
| New migration | `uv run alembic revision -m "add jobs"` → **hand-review** → `upgrade head` |
| Roll back one | `uv run alembic downgrade -1` |
| Run tests | `uv run pytest` |
| Run evals | `uv run python -m evals.run --suite cv_grounding` |
| Inspect failures | `jq -r 'select(.result=="failure")' var/logs/oscar-api.jsonl` |
| Backup now | see §5 |
| Full reset (**destructive**) | `docker compose down -v && rm -rf var/storage/*` — confirm backups first |

## Authorized Tencent installation (2026-11-09)

The operator subsequently authorized a separate VPS runtime. See [24_TENCENT_VPS.md](24_TENCENT_VPS.md) for the current HTTPS prefix, shared PostgreSQL, resource and credential contract. Earlier local-only instructions remain the development/pilot profile.
