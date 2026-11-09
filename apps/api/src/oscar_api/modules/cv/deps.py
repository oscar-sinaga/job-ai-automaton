"""FastAPI dependency providers for the CV module's ports.

Tests override `get_llm_provider` with a `FakeLLMProvider` via
`app.dependency_overrides` (docs/12 §2) -- no test ever constructs a real
`OpenAILLMProvider`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.orm import Session

from oscar_api.adapters.local_storage import LocalFileStorage
from oscar_api.adapters.openai_provider import OpenAILLMProvider
from oscar_api.config import get_settings
from oscar_api.core.errors import LLMUnavailableError
from oscar_api.db import get_session
from oscar_api.modules.settings.preferences import effective_integration
from oscar_api.ports.llm import LLMProvider
from oscar_api.ports.storage import Storage


async def get_llm_provider(session: Session = Depends(get_session)) -> AsyncIterator[LLMProvider]:
    if not get_settings().openai_api_key:
        raise LLMUnavailableError(
            "AI generation is not configured. Capture and tracking remain available."
        )
    model, max_tokens = effective_integration(session)
    provider = OpenAILLMProvider(model=model, max_output_tokens=max_tokens)
    try:
        yield provider
    finally:
        await provider.aclose()


def get_storage() -> Storage:
    return LocalFileStorage()
