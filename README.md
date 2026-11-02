# OSCAR Job Copilot

A personal job-search operating system: capture jobs in seconds, generate grounded
tailored CVs from a verified career-fact store (zero fabricated claims), track every
application and which exact CV version was sent, and see the funnel honestly.

> Automatic where automation is reliable, human-assisted where automation is fragile.

**Status (2026-11-02): M0–M5 code exists; preparing the first real-usage pilot.**
The review found gaps in CV grounding, approval, PDF rendering and download.
The fixes restrict CV claims to stored career statements, validate skills and edits,
require review before export, preserve application status, and provide a working PDF
download. The local smoke flow uses example data and a fake model; real-model quality,
phone capture and the V1 usage targets remain unverified.

Start with **[docs/18_FIRST_REAL_USAGE.md](docs/18_FIRST_REAL_USAGE.md)** for the
first 3–5 applications, then measure M6 against
[docs/15_ROADMAP_AND_MILESTONES.md](docs/15_ROADMAP_AND_MILESTONES.md).

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
evals/          CV grounding eval fixtures + harness (apps/api/scripts/) — built, never run
                against a real model in this environment (needs OPENAI_API_KEY)
docs/           The design pack — read this before touching code
```

## Before Milestone 6

Remaining open decisions in [docs/17_DECISION_LOG.md](docs/17_DECISION_LOG.md) §2 (none currently block anything): OPEN-3 (durable job queue), OPEN-4 (embedding-based retrieval), OPEN-5 (LLM provider data-retention posture — review before sending real career data to OpenAI), OPEN-6 (production hosting).

To actually start using this: set `OPENAI_API_KEY`, populate the career profile with real experience/achievements (`/career-profile`), and run `apps/api/scripts/eval_cv_grounding.py` against its two adversarial cases before trusting CV generation with a real application.
