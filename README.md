# OSCAR Job Copilot

A personal job-search operating system: capture jobs in seconds, generate grounded
tailored CVs from a verified career-fact store (zero fabricated claims), track every
application and which exact CV version was sent, and see the funnel honestly.

> Automatic where automation is reliable, human-assisted where automation is fragile.

**Status (2026-11-03): technical MVP is ready for a personal pilot, with real-model
fixture acceptance and Android emulator sharing verified.**
The review found gaps in CV grounding, approval, PDF rendering and download.
The fixes restrict CV claims to stored career statements, validate skills and edits,
require review before export, preserve application status, and provide a working PDF
download. Deterministic browser/runtime tests use a fake model. Separately, four
approved real-API cases passed with the low-cost `gpt-6-luna` model; see the
[recorded results](evals/cv_grounding/results/2026-11-03_gpt-6-luna.json).
Real career-profile quality, physical-phone compatibility and V1 usage targets
still require actual use.
Android 15 emulator tests passed native Share → HTTP Shortcuts → the capture API,
with the saved job checked in the database and on the device success screen.
See [Android setup and limits](docs/21_ANDROID_SHARE_SHORTCUT.md).

Start with **[docs/18_FIRST_REAL_USAGE.md](docs/18_FIRST_REAL_USAGE.md)** for the
first 3–5 applications, then measure M6 against
[docs/15_ROADMAP_AND_MILESTONES.md](docs/15_ROADMAP_AND_MILESTONES.md).

For a persistent local stack, use **[docs/20_MVP_PILOT.md](docs/20_MVP_PILOT.md)**.
It runs PostgreSQL, the API and a standalone Node web server with Docker Compose,
including explicit simulation mode, backup and restore verification. The CI runtime
check exercises the actual images and verifies data and PDFs after container recreation.
Normal-mode AI setup uses `python scripts/pilot.py configure-ai` with hidden terminal
input. `OSCAR_API_KEY` stays separate from the provider's `OPENAI_API_KEY`.

```bash
python scripts/pilot.py init --simulation
python scripts/pilot.py start --simulation
```

Open `http://127.0.0.1:5173`. Simulation uses example data and deterministic CV
output without AI requests. Omit `--simulation` for the normal local workspace.
The default model is `gpt-6-luna`, with no reasoning, a 4,096-output-token limit
and no automatic upgrade to a more expensive model. The real-usage targets
remain separate from the fixture acceptance result.

For testing without an API key, use **[docs/19_OFFLINE_SIMULATION.md](docs/19_OFFLINE_SIMULATION.md)**:
an isolated simulation server plus desktop/mobile-viewport browser tests. This
checks the app flow with example facts, not model quality or real applications.

## Start here

- **[docs/README.md](docs/README.md)** — the design pack and current pilot guide: PRD, architecture, data model, API design, LLM/grounding design, security, test strategy, risks, and open decisions.
- **[docs/15_ROADMAP_AND_MILESTONES.md](docs/15_ROADMAP_AND_MILESTONES.md)** — what's built, what's verified vs. not, and what M6 requires.
- **[OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md](OSCAR_Job_Copilot_AI_Agent_Master_Spec_v2.md)** — the source engineering spec.
- **[OSCAR_Job_Copilot_User_Plan_v2.md](OSCAR_Job_Copilot_User_Plan_v2.md)** — the source product plan (Indonesian).

## Stack (fixed, ADR-001)

FastAPI + PostgreSQL (backend) · SvelteKit + TypeScript + Tailwind CSS (frontend) · Python managed with `uv` · OpenAI behind a provider port (ADR-025).

## Local development

Docker runs inside WSL2 on this machine, and Windows could not reliably reach the WSL2-forwarded Postgres port during development (ADR-022) — so run everything that touches the database **from a WSL terminal**. The web app is unaffected and runs fine from Windows.

```bash
# inside WSL
cp .env.example .env                     # fill in OSCAR_API_KEY, OPENAI_API_KEY
docker compose up -d db

cd apps/api
export UV_PROJECT_ENVIRONMENT=~/.venvs/oscar-api   # keep the venv off /mnt/c (ADR-022)
uv sync
uv run alembic upgrade head
uv run uvicorn oscar_api.main:app --reload --port 8000   # http://127.0.0.1:8000/health
uv run pytest                                            # tests use a database: use a dedicated test DB
```

```bash
# from Windows (or WSL) -- proxies /api to the FastAPI server above
cd apps/web
cp .env.example .env                     # fill in API_KEY (matches OSCAR_API_KEY above)
npm install
npm run dev                                              # http://127.0.0.1:5173
```

Full runbook: [docs/14_DEPLOYMENT_PLAN.md](docs/14_DEPLOYMENT_PLAN.md). WSL rationale: [docs/17_DECISION_LOG.md](docs/17_DECISION_LOG.md) ADR-022.

## Repository layout

```text
apps/
  api/          FastAPI backend (uv-managed): jobs, career profile, CV generation +
                grounding, application tracking, analytics — 6 migrations, ~45 modules
  web/          SvelteKit + TS + Tailwind: Dashboard, Job Inbox/Detail, Career Profile,
                CV Review, Analytics, mobile share-target
  extension/    Browser extension (MV3, esbuild): one-click capture
  mobile/       Mobile capture setup instructions (PWA lives in apps/web; see apps/mobile/README.md)
agents/         LLM agent prompts (cv_generator/v2.md, selection-only pilot); job_parser not built (P1)
adapters/       Future ATS automation adapters (P3, not yet implemented)
domain/         Signpost only — domain logic lives in apps/api (see domain/README.md)
workers/        Signpost only — background tasks run in-process for now (see workers/README.md)
evals/          CV grounding fixtures + harness (apps/api/scripts/); four real-API
                GPT-6 Luna cases passed, with token usage and evidence recorded
docs/           The design pack — read this before touching code
```

## Before Milestone 6

Remaining open decisions in [docs/17_DECISION_LOG.md](docs/17_DECISION_LOG.md) §2 (none currently block anything): OPEN-3 (durable job queue), OPEN-4 (embedding-based retrieval), OPEN-5 (LLM provider data-retention posture — review before sending real career data to OpenAI), OPEN-6 (production hosting).

To actually start using this: set `OPENAI_API_KEY`, populate the career profile with real experience/achievements (`/career-profile`), and run `apps/api/scripts/eval_cv_grounding.py` against its two adversarial cases before trusting CV generation with a real application.
