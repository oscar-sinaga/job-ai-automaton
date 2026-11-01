# apps/api — OSCAR Job Copilot backend

FastAPI + PostgreSQL, managed with `uv`. Milestone 0 ships only `/health`; the
full planned surface is in [../../docs/05_API_DESIGN.md](../../docs/05_API_DESIGN.md).

## Setup

```bash
cp ../../.env.example ../../.env   # fill in secrets
docker compose -f ../../docker-compose.yml up -d db
uv sync
uv run alembic upgrade head
uv run uvicorn oscar_api.main:app --reload --port 8000
```

Verify: `curl http://127.0.0.1:8000/health`

## Commands

| Command | Purpose |
|---|---|
| `uv run pytest` | Test suite |
| `uv run ruff check .` / `uv run ruff format .` | Lint / format |
| `uv run mypy src` | Type check |
| `uv run lint-imports` | Enforce module boundaries (docs/03 §2) — contracts added starting M1, once `modules/` exists |
| `uv run alembic revision -m "..."` | New migration (hand-review autogenerate) |
| `uv run alembic upgrade head` / `downgrade -1` | Apply / roll back |

## Layout

```text
src/oscar_api/
  main.py       FastAPI app + /health
  config.py     Settings from environment (OSCAR_* / OPENAI_*)
  db.py         Engine, session, declarative Base
  modules/      (M1+) jobs, career, cv, applications, analytics
  ports/        (M3+) LLMProvider, Storage — interfaces only
  adapters/     (M3+) openai_provider.py, local_storage.py
alembic/        migrations (baseline is empty; see docs/04_DATA_MODEL.md §9)
tests/
```

See [../../docs/03_SYSTEM_ARCHITECTURE.md](../../docs/03_SYSTEM_ARCHITECTURE.md) for the dependency rules between these.
