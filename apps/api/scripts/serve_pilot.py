"""Start the local Compose pilot, with simulation only when explicitly selected."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url


def main() -> None:
    mode = os.environ.get("OSCAR_ENV", "local")
    if mode not in {"local", "simulation"}:
        raise SystemExit("The pilot supports local or simulation mode.")
    if mode == "simulation":
        os.environ["OPENAI_API_KEY"] = ""
        database = make_url(os.environ["OSCAR_DATABASE_URL"])
        if database.host != "db" or not (database.database or "").startswith("oscar_simulation_"):
            raise SystemExit("Simulation requires the isolated Compose simulation database.")
    if not os.environ.get("OSCAR_API_KEY"):
        raise SystemExit("Initialize the pilot credentials before starting the API.")

    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    command.upgrade(config, "head")

    from oscar_api.main import app

    if mode == "simulation":
        from serve_simulation import SimulationProvider

        from oscar_api.modules.cv.deps import get_llm_provider

        provider = SimulationProvider()
        app.dependency_overrides[get_llm_provider] = lambda: provider
        print("SIMULATION: CV output copies example facts; no AI requests.", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
