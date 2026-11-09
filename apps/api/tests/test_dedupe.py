"""Unit tests for URL canonicalisation and dedupe key computation.

Pure functions, no database -- these should stay fast and exhaustive since
dedupe logic is the thing most likely to need tuning as real captures reveal
new tracking-param and source-ID patterns (docs/04 §7).
"""

from __future__ import annotations

import pytest

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


@pytest.mark.parametrize(
    "route",
    ["/jobs/", "/jobs/search/", "/jobs/search-results/", "/jobs/collections/recommended/"],
)
def test_linkedin_selected_job_matches_direct_view(route: str) -> None:
    selected = (
        f"https://www.linkedin.com{route}?currentJobId=4012345678"
        "&trackingId=search-context&refId=another-context&keywords=engineering"
    )
    direct = "https://linkedin.com/jobs/view/4012345678/?trackingId=view-context"
    expected = "https://linkedin.com/jobs/view/4012345678"
    assert canonicalize_url(selected) == canonicalize_url(direct) == expected
    assert canonicalize_url(canonicalize_url(selected)) == expected
    assert compute_dedupe_key(selected) == compute_dedupe_key(direct)
    assert compute_dedupe_key(selected) == "srcid:linkedin.com:4012345678"


def test_linkedin_selected_jobs_remain_distinct() -> None:
    base = "https://www.linkedin.com/jobs/search-results/?currentJobId="
    assert compute_dedupe_key(base + "4012345678") != compute_dedupe_key(base + "4012345679")


@pytest.mark.parametrize("host", ["www.linkedin.com", "id.linkedin.com", "LINKEDIN.COM"])
def test_linkedin_view_uses_one_host_and_drops_all_query_params(host: str) -> None:
    url = f"http://{host}/jobs/view/4012345678/?refId=123&trackingId=456&foo=bar#details"
    assert canonicalize_url(url) == "https://linkedin.com/jobs/view/4012345678"
    assert compute_dedupe_key(url) == "srcid:linkedin.com:4012345678"


def test_linkedin_direct_view_id_takes_precedence_over_stale_selection() -> None:
    url = "https://linkedin.com/jobs/view/4012345678/?currentJobId=4012345679"
    assert canonicalize_url(url) == "https://linkedin.com/jobs/view/4012345678"


@pytest.mark.parametrize(
    "query",
    [
        "currentJobId=4012345678&currentJobId=4012345679",
        "currentJobId=4012345678&currentJobId=4012345678",
        "currentJobId=&currentJobId=4012345678",
        "currentJobId=",
        "currentJobId=not-a-number",
        "currentJobId=4012345678extra",
        "currentJobId=%204012345678",
        "currentJobId=%EF%BC%94%EF%BC%90%EF%BC%91",
    ],
)
def test_linkedin_ambiguous_or_malformed_selection_is_not_a_job_id(query: str) -> None:
    url = f"https://linkedin.com/jobs/search-results/?{query}"
    canonical = canonicalize_url(url)
    assert canonical.startswith("https://linkedin.com/jobs/search-results")
    assert extract_source_job_id(canonical) is None
    assert compute_dedupe_key(url).startswith("url:")


@pytest.mark.parametrize(
    "host", ["notlinkedin.com", "linkedin.com.example.com", "linkedin.com@evil.example"]
)
@pytest.mark.parametrize("route", ["/jobs/view/4012345678", "/jobs/search?currentJobId=4012345678"])
def test_linkedin_lookalike_host_is_not_a_linkedin_job(host: str, route: str) -> None:
    url = f"https://{host}{route}"
    assert canonicalize_url(url) == url
    assert extract_source_job_id(url) is None
    assert compute_dedupe_key(url) == f"url:{url}"


@pytest.mark.parametrize("route", ["/feed", "/company/example", "/jobs/view/not-a-number"])
def test_linkedin_selection_id_outside_selected_job_routes_is_not_used(route: str) -> None:
    url = f"https://linkedin.com{route}?currentJobId=4012345678"
    assert canonicalize_url(url) == url
    assert extract_source_job_id(canonicalize_url(url)) is None


def test_unknown_site_retains_selection_query_parameter() -> None:
    url = "https://careers.example.com/jobs/search?currentJobId=123&ref=abc&utm_source=share"
    canonical = "https://careers.example.com/jobs/search?currentJobId=123&ref=abc"
    assert canonicalize_url(url) == canonical
    assert extract_source_job_id(canonical) is None
    assert compute_dedupe_key(url) == f"url:{canonical}"


def test_linkedin_view_id_must_be_entire_path_segment() -> None:
    url = "https://linkedin.com/jobs/view/4012345678extra"
    assert extract_source_job_id(url) is None
    assert compute_dedupe_key(url) == f"url:{url}"


@pytest.mark.parametrize(
    "route",
    [
        "/jobs/view/synthetic-research-lead-4012345678",
        "/jobs/view/synthetic-research-lead-4012345678/",
    ],
)
def test_linkedin_public_slug_numeric_and_search_urls_share_identity(route: str) -> None:
    slug = f"https://www.linkedin.com{route}?currentJobId=4012345679&trk=public"
    numeric = "https://linkedin.com/jobs/view/4012345678"
    search = "https://linkedin.com/jobs/search-results?currentJobId=4012345678"
    assert canonicalize_url(slug) == canonicalize_url(search) == numeric
    assert canonicalize_url(canonicalize_url(slug)) == numeric
    assert extract_source_job_id(slug) == "4012345678"
    assert compute_dedupe_key(slug) == compute_dedupe_key(numeric) == compute_dedupe_key(search)


@pytest.mark.parametrize(
    "route",
    [
        "/jobs/view/synthetic-research-lead",
        "/jobs/view/synthetic-research-lead-4012345678extra",
        "/jobs/view/synthetic-research-lead-4012345678/extra",
        "/jobs/view/synthetic-research-lead-4012345678//",
        "/jobs/view/synthetic-research-lead-4012345678;extra",
        "/jobs/view/synthetic-research-lead-\uff14\uff10\uff11",
    ],
)
def test_linkedin_title_link_without_a_valid_trailing_id_is_not_identity(route: str) -> None:
    url = f"https://linkedin.com{route}?currentJobId=4012345679"
    canonical = canonicalize_url(url)
    assert extract_source_job_id(url) is None
    assert extract_source_job_id(canonical) is None
    assert canonicalize_url(canonical) == canonical
    assert compute_dedupe_key(url).startswith("url:")


def test_linkedin_slug_on_lookalike_domain_is_not_identity() -> None:
    url = "https://linkedin.com.example.com/jobs/view/synthetic-research-lead-4012345678"
    assert canonicalize_url(url) == url
    assert extract_source_job_id(url) is None
    assert compute_dedupe_key(url) == f"url:{url}"


def test_linkedin_blank_duplicate_id_stays_ambiguous_after_recanonicalization() -> None:
    url = "https://linkedin.com/jobs/search?currentJobId=&currentJobId=4012345678"
    canonical = canonicalize_url(url)
    assert canonicalize_url(canonical) == canonical
    assert extract_source_job_id(canonical) is None
    assert compute_dedupe_key(url).startswith("url:")


@pytest.mark.parametrize(
    "route",
    [
        "/",
        "/id/",
        "/jobs",
        "/jobs-in-Indonesia/",
        "/data-scientist-jobs",
        "/data-scientist-jobs/in-Jakarta",
        "/data-scientist-jobs/in-Jakarta/full-time/",
        "/id/data-scientist-jobs/in-Jakarta/contract-temp",
    ],
)
def test_jobstreet_selected_job_matches_direct_view(route: str) -> None:
    selected = f"https://id.jobstreet.com{route}?jobId=95264526&type=standard&page=2"
    direct = "https://id.jobstreet.com/job/95264526?origin=cardTitle&ref=search-standalone"
    expected = "https://id.jobstreet.com/job/95264526"
    assert canonicalize_url(selected) == canonicalize_url(direct) == expected
    assert canonicalize_url(expected) == expected
    assert extract_source_job_id(selected) == "95264526"
    assert compute_dedupe_key(selected) == compute_dedupe_key(direct)
    assert compute_dedupe_key(selected) == "srcid:id.jobstreet.com:95264526"


@pytest.mark.parametrize(
    "host",
    ["id.jobstreet.com", "ID.JOBSTREET.COM", "jobstreet.co.id", "www.jobstreet.co.id"],
)
@pytest.mark.parametrize("route", ["/job/95264526", "/id/job/95264526/"])
def test_jobstreet_indonesian_legacy_and_current_urls_match(host: str, route: str) -> None:
    url = f"http://{host}{route}?ref=search&type=standard#details"
    assert canonicalize_url(url) == "https://id.jobstreet.com/job/95264526"
    assert extract_source_job_id(url) == "95264526"
    assert compute_dedupe_key(url) == "srcid:id.jobstreet.com:95264526"


@pytest.mark.parametrize("host", ["jobstreet.com", "www.jobstreet.com", "my.jobstreet.com"])
def test_jobstreet_other_hosts_keep_their_market_identity(host: str) -> None:
    canonical_host = host.removeprefix("www.")
    url = f"https://{host}/job/95264526?origin=cardTitle"
    assert canonicalize_url(url) == f"https://{canonical_host}/job/95264526"
    assert compute_dedupe_key(url) == f"srcid:{canonical_host}:95264526"
    assert compute_dedupe_key(url) != compute_dedupe_key("https://id.jobstreet.com/job/95264526")


def test_jobstreet_direct_view_takes_precedence_over_stale_selected_query() -> None:
    url = "https://id.jobstreet.com/job/95264526?jobId=95264527&jobId=95264528"
    assert canonicalize_url(url) == "https://id.jobstreet.com/job/95264526"
    assert extract_source_job_id(url) == "95264526"


def test_jobstreet_selected_jobs_remain_distinct() -> None:
    base = "https://id.jobstreet.com/data-scientist-jobs?jobId="
    assert compute_dedupe_key(base + "95264526") != compute_dedupe_key(base + "95264527")


@pytest.mark.parametrize(
    "query",
    [
        "jobId=95264526&jobId=95264527",
        "jobId=95264526&jobId=95264526",
        "jobId=&jobId=95264526",
        "jobId=95264526&jobId",
        "jobId=",
        "jobId=not-a-number",
        "jobId=95264526extra",
        "jobId=%2095264526",
        "jobId=95264526%20",
        "jobId=%EF%BC%99%EF%BC%95%EF%BC%92",
        "jobId=%D9%A9%D9%A5%D9%A2",
        "jobid=95264526",
    ],
)
def test_jobstreet_ambiguous_or_malformed_selection_is_not_a_job_id(query: str) -> None:
    url = f"https://id.jobstreet.com/data-scientist-jobs?{query}"
    assert extract_source_job_id(url) is None
    assert extract_source_job_id(canonicalize_url(url)) is None
    assert compute_dedupe_key(url).startswith("url:")


@pytest.mark.parametrize(
    "route",
    [
        "/job/95264526extra",
        "/job/95264526/extra",
        "/job/\uff19\uff15\uff12\uff16\uff14\uff15\uff12\uff16",
        "/job/%39%35%32%36%34%35%32%36",
        "/job/95264526//",
        "/job/95264526;extra",
        "/jobs/95264526",
        "/account",
        "/companies/example",
        "/companies/example-jobs",
        "/job/",
        "/unknown-route",
        "/data-scientist-jobs/arbitrary-detail",
        "/data-scientist-jobs//",
    ],
)
def test_jobstreet_job_id_requires_a_recognized_entire_path(route: str) -> None:
    url = f"https://id.jobstreet.com{route}?jobId=95264527"
    assert extract_source_job_id(url) is None
    assert extract_source_job_id(canonicalize_url(url)) is None
    assert compute_dedupe_key(url).startswith("url:")


@pytest.mark.parametrize(
    "host",
    [
        "notjobstreet.com",
        "jobstreet.com.example.com",
        "jobstreet.co.id.example.com",
        "jobstreet.example.com",
        "jobstreet.com@evil.example",
        "jobstreet.co.id@evil.example",
    ],
)
@pytest.mark.parametrize("route", ["/job/95264526", "/data-scientist-jobs?jobId=95264526"])
def test_jobstreet_lookalike_host_is_not_a_jobstreet_job(host: str, route: str) -> None:
    url = f"https://{host}{route}"
    assert canonicalize_url(url) == url
    assert extract_source_job_id(url) is None
    assert compute_dedupe_key(url) == f"url:{url}"


def test_jobstreet_embedded_job_url_is_not_a_source_id() -> None:
    url = "https://id.jobstreet.com/account?return=/job/95264526"
    assert extract_source_job_id(url) is None
    assert extract_source_job_id(canonicalize_url(url)) is None
    assert compute_dedupe_key(url).startswith("url:")


def test_unknown_site_retains_jobstreet_selection_parameter() -> None:
    url = "https://careers.example.com/jobs?jobId=95264526&ref=abc&utm_source=share"
    expected = "https://careers.example.com/jobs?jobId=95264526&ref=abc"
    assert canonicalize_url(url) == expected
    assert extract_source_job_id(expected) is None
    assert compute_dedupe_key(url) == f"url:{expected}"


@pytest.mark.parametrize("scheme", ["ftp", "file"])
def test_jobstreet_non_web_scheme_is_not_a_source_id(scheme: str) -> None:
    url = f"{scheme}://id.jobstreet.com/job/95264526"
    assert extract_source_job_id(url) is None
    assert compute_dedupe_key(url) == f"url:{url}"
