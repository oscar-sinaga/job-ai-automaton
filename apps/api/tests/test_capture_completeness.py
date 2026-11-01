"""Unit tests for server-derived capture completeness (ADR-012, docs/05 §3).

The client's claim is never trusted -- `CaptureEnvelope` has no completeness
field at all, so these tests exercise the one function that decides it.
"""

from __future__ import annotations

import datetime as dt

from oscar_api.modules.jobs.models import CaptureCompleteness, CaptureMethod
from oscar_api.modules.jobs.schemas import CaptureEnvelope
from oscar_api.modules.jobs.service import derive_capture_completeness

NOW = dt.datetime.now(dt.UTC)
LONG_TEXT = "Senior ML Engineer role. " * 10  # well past the completeness floor


def _envelope(**overrides: object) -> CaptureEnvelope:
    defaults: dict[str, object] = {
        "url": "https://example.com/jobs/1",
        "captured_at": NOW,
        "capture_method": CaptureMethod.extension,
    }
    defaults.update(overrides)
    return CaptureEnvelope(**defaults)  # type: ignore[arg-type]


def test_complete_when_raw_text_present() -> None:
    envelope = _envelope(raw_text=LONG_TEXT)
    assert derive_capture_completeness(envelope) == CaptureCompleteness.CAPTURED_COMPLETE


def test_complete_when_only_selected_text_present() -> None:
    envelope = _envelope(raw_text=None, selected_text=LONG_TEXT)
    assert derive_capture_completeness(envelope) == CaptureCompleteness.CAPTURED_COMPLETE


def test_complete_when_only_shared_text_present() -> None:
    envelope = _envelope(
        capture_method=CaptureMethod.mobile_share, raw_text=None, shared_text=LONG_TEXT
    )
    assert derive_capture_completeness(envelope) == CaptureCompleteness.CAPTURED_COMPLETE


def test_partial_when_mobile_share_has_no_text() -> None:
    envelope = _envelope(capture_method=CaptureMethod.mobile_share, page_title="ML Engineer")
    assert derive_capture_completeness(envelope) == CaptureCompleteness.CAPTURED_PARTIAL


def test_partial_when_extension_capture_yields_only_a_few_characters() -> None:
    # Just a stray "N/A" or similar -- not a real JD, so not COMPLETE either.
    envelope = _envelope(raw_text="N/A")
    assert derive_capture_completeness(envelope) == CaptureCompleteness.CAPTURED_PARTIAL


def test_needs_enrichment_when_manual_url_has_no_text_at_all() -> None:
    envelope = _envelope(capture_method=CaptureMethod.manual_url)
    assert derive_capture_completeness(envelope) == CaptureCompleteness.NEEDS_ENRICHMENT


def test_manual_url_with_pasted_text_is_complete() -> None:
    envelope = _envelope(capture_method=CaptureMethod.manual_url, raw_text=LONG_TEXT)
    assert derive_capture_completeness(envelope) == CaptureCompleteness.CAPTURED_COMPLETE


def test_client_cannot_assert_completeness() -> None:
    """CaptureEnvelope has no completeness field -- this is a schema-shape
    guarantee, not just a behavioural one."""
    assert "capture_completeness" not in CaptureEnvelope.model_fields
