"""OpenAI implementation of the `LLMProvider` port (docs/06_AI_LLM_DESIGN.md, ADR-025).

The only file in this codebase that imports `openai`. Uses the Responses API's
`.parse()` helper for schema-constrained structured output (the same mechanism
`messages.parse()` played on the Anthropic SDK this replaces).

`gpt-4.1` (the configured default, ADR-025) is not a reasoning model, so the
port's `effort` parameter has nothing to map to here and is accepted but
ignored -- see the module docstring note below rather than silently
mis-mapping it to something that would change behaviour unexpectedly.
"""

from __future__ import annotations

import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from openai.types.responses import EasyInputMessageParam
from openai.types.responses.response_output_message import ResponseOutputMessage
from openai.types.responses.response_output_refusal import ResponseOutputRefusal

from oscar_api.config import get_settings
from oscar_api.ports.llm import ContentBlock, LLMProviderError, LLMRefusalError, LLMResult, T

# Non-streaming default; CV generation output (summary + several bullets +
# missing_requirements) comfortably fits (docs/06 §9 latency targets assume
# this, not a much larger output budget).
_MAX_OUTPUT_TOKENS = 16000


class OpenAILLMProvider:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        # A user-initiated generation has one bounded attempt. Hidden retries
        # can otherwise exceed the UI's timeout and issue extra paid calls.
        self._client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0)
        self._model = model or settings.llm_model

    async def aclose(self) -> None:
        await self._client.close()

    async def structured(
        self,
        *,
        system: list[ContentBlock],
        user: str,
        output_model: type[T],
        prompt_version: str,
        effort: str = "high",  # accepted for port compatibility, unused -- see module docstring
        timeout_s: float = 90.0,
    ) -> LLMResult:
        input_messages: list[EasyInputMessageParam] = [
            {"role": "system", "content": block.text} for block in system
        ]
        input_messages.append({"role": "user", "content": user})

        started = time.monotonic()
        try:
            response = await self._client.responses.parse(
                model=self._model,
                # `list` is invariant; the SDK's broader input union rejects
                # these valid message dictionaries at type-check time only.
                input=input_messages,  # type: ignore[arg-type]
                text_format=output_model,
                timeout=timeout_s,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
                store=False,
            )
        except AuthenticationError as exc:
            raise LLMProviderError(
                "authentication", "OpenAI authentication failed. Check OPENAI_API_KEY."
            ) from exc
        except RateLimitError as exc:
            if exc.code == "insufficient_quota":
                raise LLMProviderError(
                    "quota", "OpenAI quota is unavailable. Check API billing and project limits."
                ) from exc
            raise LLMProviderError(
                "rate_limit", "OpenAI is rate limiting requests. Wait briefly before retrying."
            ) from exc
        except APITimeoutError as exc:
            raise LLMProviderError("timeout", "OpenAI timed out. Please retry.") from exc
        except APIConnectionError as exc:
            raise LLMProviderError(
                "connection", "Cannot reach OpenAI. Check the server's network connection."
            ) from exc
        except APIStatusError as exc:
            raise LLMProviderError(
                "provider", "OpenAI could not complete generation. Check model access or retry."
            ) from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        # A refusal can show up two ways: the whole response marked incomplete
        # with a content_filter reason, or an individual output item carrying
        # a `refusal` content block instead of a parsed one.
        if (
            response.status == "incomplete"
            and response.incomplete_details
            and response.incomplete_details.reason == "content_filter"
        ):
            raise LLMRefusalError("content_filter")
        for item in response.output:
            if not isinstance(item, ResponseOutputMessage):
                continue
            for content in item.content:
                if isinstance(content, ResponseOutputRefusal):
                    raise LLMRefusalError(content.refusal)

        if response.output_parsed is None:
            raise RuntimeError("Model response did not match the requested output schema")

        usage = response.usage
        cache_read_tokens = 0
        if usage is not None and usage.input_tokens_details is not None:
            cache_read_tokens = usage.input_tokens_details.cached_tokens or 0

        return LLMResult(
            parsed=response.output_parsed.model_dump(mode="json"),
            model_name=response.model or self._model,
            prompt_version=prompt_version,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            cache_read_tokens=cache_read_tokens,
            latency_ms=latency_ms,
            request_id=response.id,
        )
