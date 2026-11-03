"""Application settings, loaded from the environment (docs/14 §3).

No secret has a default value: a missing ``OSCAR_API_KEY`` or ``OPENAI_API_KEY``
must fail loudly (at the point of use) rather than silently fall back to something
insecure.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# repo root: .../job-ai-automaton (this file is apps/api/src/oscar_api/config.py)
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OSCAR_",
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://oscar:oscar@127.0.0.1:5432/oscar"

    # Shared secret for web/extension/mobile clients (docs/03 §4, ADR-002).
    # Empty is tolerated only so that Milestone 0 runs before a .env exists;
    # from M1, request auth depends on it and an empty value rejects every write.
    api_key: str = ""

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173"]
    )

    storage_dir: Path = REPO_ROOT / "var" / "storage"
    log_dir: Path = REPO_ROOT / "var" / "logs"

    # Analytics bucket boundaries follow the user's local day, not UTC (docs/10 §7).
    timezone: str = "Asia/Jakarta"

    # ── LLM (docs/06, ADR-025) ───────────────────────────────────────────────
    # No OSCAR_ prefix -- this is the OpenAI SDK's own conventional env var
    # name, kept as-is so `openai.AsyncOpenAI()` picks it up unprompted in any
    # script that doesn't go through this settings object.
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    llm_model: str = "gpt-6-luna"
    llm_parser_model: str = "gpt-6-luna"
    llm_max_output_tokens: int = Field(default=4096, ge=512, le=16000)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """Accept a comma-separated string so .env stays simple."""
        if isinstance(v, str):
            if v.lstrip().startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
