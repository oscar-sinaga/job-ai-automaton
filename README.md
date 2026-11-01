# OSCAR Job Copilot

A personal job-search operating system: capture jobs in seconds, generate grounded
tailored CVs from a verified career-fact store (zero fabricated claims), track every
application and which exact CV version was sent, and see the funnel honestly.

> Automatic where automation is reliable, human-assisted where automation is fragile.

**Status: all five P0 build milestones (M1–M5) are done.** Capture, career profile,
grounded CV generation, application tracking, and analytics all work end-to-end —
216 tests passing, migrations verified, both apps type-check and build clean. What's
left is **Milestone 6: real usage** — populate the career profile with real data, job-hunt
with the tool, and measure against the V1 Definition of Done. That needs the product
owner's own time and a real `OPENAI_API_KEY` (CV generation has never been run
against a real model in this environment — see docs/15 §M3). See
[docs/15_ROADMAP_AND_MILESTONES.md](docs/15_ROADMAP_AND_MILESTONES.md).

## Start here

- **[docs/README.md](docs/README.md)** — the full design pack (17 documents): PRD, architecture, data model, API design, LLM/grounding design, security, test strategy, risks, and open decisions.
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
uv run pytest                                            # 216 tests
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
agents/         LLM agent prompts (cv_generator/v1.md); job_parser not built (P1)
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
