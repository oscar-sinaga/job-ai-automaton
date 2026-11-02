"""FastAPI dependency providers for the CV module's ports.

Tests override `get_llm_provider` with a `FakeLLMProvider` via
`app.dependency_overrides` (docs/12 §2) -- no test ever constructs a real
`OpenAILLMProvider`.
"""

from __future__ import annotations

from oscar_api.adapters.local_storage import LocalFileStorage
from oscar_api.adapters.openai_provider import OpenAILLMProvider
from oscar_api.config import get_settings
from oscar_api.core.errors import LLMUnavailableError
from oscar_api.ports.llm import LLMProvider
from oscar_api.ports.storage import Storage


def get_llm_provider() -> LLMProvider:
    if not get_settings().openai_api_key:
        raise LLMUnavailableError(
            "AI generation is not configured. Capture and tracking remain available."
        )
    return OpenAILLMProvider()


def get_storage() -> Storage:
    return LocalFileStorage()
