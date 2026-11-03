"""Exercise the shipped SDK adapter without network requests or API credentials."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

from oscar_api.adapters import openai_provider
from oscar_api.config import get_settings
from oscar_api.modules.cv.schemas import CVDraft, DraftBullet
from oscar_api.ports.llm import ContentBlock, LLMProviderError


def _provider(monkeypatch, *, error=None):
    draft = CVDraft(summary=DraftBullet(text="Stored statement", supporting_fact_ids=["ach_1"]))
    parse = AsyncMock(
        return_value=SimpleNamespace(
            status="completed",
            output=[],
            output_parsed=draft,
            model="fixture-model",
            id="fixture-response",
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=40,
                input_tokens_details=SimpleNamespace(cached_tokens=20),
            ),
        ),
        side_effect=error,
    )
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse), close=AsyncMock())
    constructors = []
    monkeypatch.setattr(get_settings(), "openai_api_key", "synthetic-test-only-key")

    def create(**kwargs):
        constructors.append(kwargs)
        return client

    monkeypatch.setattr(openai_provider, "AsyncOpenAI", create)
    return openai_provider.OpenAILLMProvider(), client, constructors


async def _generate(provider):
    return await provider.structured(
        system=[ContentBlock(text="Fixture instructions")],
        user="Fixture job description",
        output_model=CVDraft,
        prompt_version="fixture-v1",
        timeout_s=12,
    )


async def test_adapter_limits_calls_and_disables_response_storage(monkeypatch):
    provider, client, constructors = _provider(monkeypatch)
    result = await _generate(provider)
    arguments = client.responses.parse.call_args.kwargs
    assert constructors[0]["max_retries"] == 0
    assert arguments["store"] is False
    assert arguments["max_output_tokens"] == 16000
    assert arguments["timeout"] == 12
    assert result.parsed["summary"]["supporting_fact_ids"] == ["ach_1"]
    assert result.cache_read_tokens == 20
    await provider.aclose()
    client.close.assert_awaited_once()


@pytest.mark.parametrize("kind", ["authentication", "quota", "rate_limit", "timeout", "connection"])
async def test_adapter_maps_errors_without_echoing_provider_text(monkeypatch, kind):
    request = httpx.Request("POST", "https://example.com/fixture")
    raw = "private upstream response and credential material"
    if kind == "authentication":
        error = AuthenticationError(raw, response=httpx.Response(401, request=request), body={})
    elif kind in {"quota", "rate_limit"}:
        error = RateLimitError(
            raw,
            response=httpx.Response(429, request=request),
            body={"code": "insufficient_quota" if kind == "quota" else "rate_limit_exceeded"},
        )
    elif kind == "timeout":
        error = APITimeoutError(request=request)
    else:
        error = APIConnectionError(message=raw, request=request)
    provider, _, _ = _provider(monkeypatch, error=error)
    with pytest.raises(LLMProviderError) as caught:
        await _generate(provider)
    assert caught.value.category == kind
    assert raw not in str(caught.value)
