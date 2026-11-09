"""Test doubles for the LLM and storage ports (docs/12 §2: no test calls a
real model or touches the real filesystem location)."""

from __future__ import annotations

from typing import Any

from oscar_api.ports.llm import ContentBlock, LLMResult


class FakeLLMProvider:
    """Returns pre-queued responses in order. Records every call it received
    so a test can assert what the caller actually sent (e.g. that the career
    facts were placed after the cache breakpoint)."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def queue(self, response: dict[str, Any]) -> None:
        self._responses.append(response)

    async def structured(
        self,
        *,
        system: list[ContentBlock],
        user: str,
        output_model: type,
        prompt_version: str,
        effort: str = "high",
        timeout_s: float = 90.0,
    ) -> LLMResult:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "output_model": output_model,
                "prompt_version": prompt_version,
                "effort": effort,
            }
        )
        if not self._responses:
            raise RuntimeError("FakeLLMProvider has no queued responses left")
        data = self._responses.pop(0)
        validated = output_model.model_validate(data)
        return LLMResult(
            parsed=validated.model_dump(mode="json"),
            model_name="fake-model",
            prompt_version=prompt_version,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=0,
            latency_ms=1,
        )


class FailingLLMProvider:
    """Always raises, to exercise the LLM_UNAVAILABLE path."""

    async def structured(self, **_: object) -> LLMResult:
        raise TimeoutError("simulated provider timeout")


class InMemoryStorage:
    """Never touches disk -- keeps PDF-export tests independent of `var/storage/`."""

    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    def save(self, *, relative_path: str, data: bytes) -> str:
        self.saved[relative_path] = data
        return f"memory://{relative_path}"

    def load(self, uri: str) -> bytes:
        return self.saved[uri.removeprefix("memory://")]

    def iter_load(self, uri: str):
        yield self.load(uri)

    def delete(self, uri: str) -> None:
        self.saved.pop(uri.removeprefix("memory://"), None)
