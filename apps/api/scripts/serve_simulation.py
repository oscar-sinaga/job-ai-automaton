"""Serve the real API with a deterministic, network-free CV provider.

Only a loopback PostgreSQL database named oscar_simulation_* is accepted.
Migrations run on that database; nothing is seeded or deleted automatically.
This is an explicit test entry point, never a production provider fallback.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy.engine import make_url

from oscar_api.ports.llm import ContentBlock, LLMResult

T = TypeVar("T", bound=BaseModel)


class SimulationProvider:
    """Copy supplied facts without ranking, paraphrasing or external requests."""

    async def structured(
        self,
        *,
        system: list[ContentBlock],
        user: str,
        output_model: type[T],
        prompt_version: str,
        effort: str = "high",
        timeout_s: float = 90.0,
    ) -> LLMResult:
        facts = json.loads(system[-1].text)
        experience: dict[int, list[dict[str, object]]] = {}
        projects: dict[int, list[dict[str, object]]] = {}
        skills: set[str] = set()
        for fact in facts:
            bullet = {"text": fact["statement"], "supporting_fact_ids": [fact["fact_id"]]}
            if fact["experience_id"] is not None:
                experience.setdefault(fact["experience_id"], []).append(bullet)
            elif fact["project_id"] is not None:
                projects.setdefault(fact["project_id"], []).append(bullet)
            skills.update(fact["skill_tags"] + fact["technology_tags"])
        draft = output_model.model_validate(
            {
                "summary": {
                    "text": facts[0]["statement"],
                    "supporting_fact_ids": [facts[0]["fact_id"]],
                },
                "experience": [
                    {"experience_id": key, "bullets": bullets}
                    for key, bullets in experience.items()
                ],
                "projects": [
                    {"project_id": key, "bullets": bullets} for key, bullets in projects.items()
                ],
                "skills": sorted(skills),
                "missing_requirements": [
                    "SIMULATION ONLY: job fit and missing requirements have not been evaluated."
                ],
            }
        )
        return LLMResult(
            parsed=draft.model_dump(mode="json"),
            model_name="simulation-no-api",
            prompt_version=prompt_version,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            latency_ms=0,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--storage-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or not (url.database or "").startswith("oscar_simulation_")
        or url.query
    ):
        parser.error(
            "Use a loopback PostgreSQL database named oscar_simulation_* (no URL options)."
        )
    os.environ.update(
        OSCAR_ENV="simulation",
        OSCAR_DATABASE_URL=args.database_url,
        OSCAR_STORAGE_DIR=str(args.storage_dir.resolve()),
        OSCAR_API_KEY="simulation-only-key",
        OPENAI_API_KEY="",
    )

    import uvicorn
    from alembic import command
    from alembic.config import Config

    from oscar_api.main import app
    from oscar_api.modules.cv.deps import get_llm_provider

    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    command.upgrade(config, "head")
    provider = SimulationProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    print("SIMULATION ONLY: no OpenAI requests; use example career data.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
