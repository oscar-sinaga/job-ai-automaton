"""The LLM provider port (docs/06_AI_LLM_DESIGN.md §1).

Nothing in `modules/` imports `openai` directly -- only `adapters/openai_provider.py`
does (ADR-025). Tests inject `FakeLLMProvider` (in `tests/fakes.py`) so the entire
grounding pipeline is testable without network access or spending money (docs/12 §2).
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ContentBlock(BaseModel):
    """A minimal system-block shape. `cache_control` is a no-op for the
    OpenAI adapter (its prompt caching is automatic based on prefix
    stability, no explicit breakpoint needed -- docs/06 §5); kept on the
    port in case a future adapter needs it."""

    type: str = "text"
    text: str
    cache_control: dict[str, Any] | None = None


class LLMResult(BaseModel):
    parsed: dict[str, Any]
    model_name: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    latency_ms: int
    request_id: str | None = None


class LLMRefusalError(Exception):
    """`stop_reason == "refusal"` (docs/06 §6) -- distinct from a timeout or a
    schema-validation failure so callers can log/handle it separately."""

    def __init__(self, category: str | None) -> None:
        self.category = category
        super().__init__(f"Model refused (category={category})")


class LLMProviderError(Exception):
    """A provider failure with a safe message, never its raw request/response."""

    def __init__(self, category: str, message: str) -> None:
        self.category = category
        super().__init__(message)


class LLMProvider(Protocol):
    async def structured(
        self,
        *,
        system: list[ContentBlock],
        user: str,
        output_model: type[T],
        prompt_version: str,
        effort: str = "none",
        timeout_s: float = 90.0,
    ) -> LLMResult: ...
