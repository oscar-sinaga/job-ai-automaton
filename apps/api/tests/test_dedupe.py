"""Unit tests for URL canonicalisation and dedupe key computation.

Pure functions, no database -- these should stay fast and exhaustive since
dedupe logic is the thing most likely to need tuning as real captures reveal
new tracking-param and source-ID patterns (docs/04 §7).
"""

from __future__ import annotations

from oscar_api.modules.jobs.dedupe import (
    canonicalize_url,
    compute_dedupe_key,
    extract_source_job_id,
)


def test_canonicalize_strips_tracking_params() -> None:
    url = "https://www.LinkedIn.com/jobs/view/4012345678/?utm_source=share&gclid=abc"
    assert canonicalize_url(url) == "https://linkedin.com/jobs/view/4012345678"


def test_canonicalize_keeps_non_tracking_query_params() -> None:
    url = "https://example.com/jobs?ref=xyz&utm_campaign=foo"
    assert canonicalize_url(url) == "https://example.com/jobs?ref=xyz"


def test_canonicalize_drops_fragment_and_trailing_slash() -> None:
    assert canonicalize_url("https://example.com/jobs/123/#apply") == "https://example.com/jobs/123"


def test_canonicalize_is_idempotent() -> None:
    url = "https://www.linkedin.com/jobs/view/4012345678/?utm_source=share"
    once = canonicalize_url(url)
    assert canonicalize_url(once) == once


def test_extract_linkedin_job_id() -> None:
    canonical = canonicalize_url("https://linkedin.com/jobs/view/4012345678/")
    assert extract_source_job_id(canonical) == "4012345678"


def test_extract_returns_none_for_unknown_source() -> None:
    canonical = canonicalize_url("https://careers.example.com/jobs/ml-engineer")
    assert extract_source_job_id(canonical) is None


def test_dedupe_key_prefers_source_job_id() -> None:
    key = compute_dedupe_key("https://linkedin.com/jobs/view/4012345678/?utm_source=x")
    assert key == "srcid:linkedin.com:4012345678"


def test_dedupe_key_same_job_id_different_tracking_params_matches() -> None:
    a = compute_dedupe_key("https://linkedin.com/jobs/view/4012345678/?utm_source=email")
    b = compute_dedupe_key("https://linkedin.com/jobs/view/4012345678/?utm_source=app")
    assert a == b


def test_dedupe_key_falls_back_to_company_and_title() -> None:
    key = compute_dedupe_key(
        "https://careers.example.com/postings/123",
        company="Acme Corp",
        title="ML Engineer",
        location="Jakarta",
    )
    assert key == "ct:acme-corp:ml-engineer:jakarta"


def test_dedupe_key_falls_back_to_url_when_no_company_or_title() -> None:
    key = compute_dedupe_key("https://careers.example.com/postings/123")
    assert key == "url:https://careers.example.com/postings/123"
