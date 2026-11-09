"""URL canonicalisation and dedupe key computation (docs/04_DATA_MODEL.md §7).

Pure functions, deliberately independent of the database and the ORM, so they
can be unit-tested in isolation -- this is the logic most likely to need tuning
as real captures reveal new tracking-param and source-ID patterns.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid")
_LINKEDIN_VIEW_PATH = re.compile(r"/jobs/view/(?:[^/]+-)?([0-9]+)/?")
_LINKEDIN_SELECTED_JOB_PATH = re.compile(
    r"/jobs(?:/(?:search|search-results|collections(?:/[^/]+)?))?/?"
)
_JOBSTREET_VIEW_PATH = re.compile(r"/(?:id/)?job/([0-9]+)/?")
_JOBSTREET_SELECTED_JOB_PATH = re.compile(
    r"/(?:id/)?(?:jobs|jobs-in-[^/]+|[^/]+-jobs(?:/in-[^/]+)?)"
    r"(?:/(?:full-time|part-time|contract-temp|casual-vacation))?/?"
)

# Source-specific job-ID extraction. Each pattern is matched against the
# canonicalised URL; the first capturing group is the source's own job ID.
# Intentionally small and additive -- a source with no pattern here just falls
# through to the company+title key, never blocking capture (docs/04 §7).
_SOURCE_ID_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("glints.com", re.compile(r"/job/[^/]+/([a-zA-Z0-9]+)")),
]


def _is_tracking_param(key: str) -> bool:
    key_lower = key.lower()
    return any(key_lower.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)


def _is_linkedin_host(host: str) -> bool:
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def _linkedin_job_id(path: str, query: str) -> str | None:
    # A direct view URL identifies the posting even if a stale search parameter
    # is present. Search/collection pages instead identify the open detail panel
    # with currentJobId; never infer that ID from another link in the page.
    if match := _LINKEDIN_VIEW_PATH.fullmatch(path):
        return match.group(1)
    if not _LINKEDIN_SELECTED_JOB_PATH.fullmatch(path):
        return None
    ids = [
        value for key, value in parse_qsl(query, keep_blank_values=True) if key == "currentJobId"
    ]
    if len(ids) == 1 and re.fullmatch(r"[0-9]+", ids[0]):
        return ids[0]
    return None


def _jobstreet_host(host: str) -> str | None:
    # The Indonesian legacy domain and its replacement represent one market.
    # Keep other regional Jobstreet hosts distinct; do not assume cross-market
    # numeric IDs identify the same vacancy.
    if host == "jobstreet.co.id" or host.endswith(".jobstreet.co.id"):
        return "id.jobstreet.com"
    if host == "jobstreet.com" or host.endswith(".jobstreet.com"):
        return host.removeprefix("www.")
    return None


def _jobstreet_job_id(path: str, query: str) -> str | None:
    if match := _JOBSTREET_VIEW_PATH.fullmatch(path):
        return match.group(1)
    if path not in {"/", "/id", "/id/"} and not _JOBSTREET_SELECTED_JOB_PATH.fullmatch(path):
        return None
    ids = [value for key, value in parse_qsl(query, keep_blank_values=True) if key == "jobId"]
    if len(ids) == 1 and re.fullmatch(r"[0-9]+", ids[0]):
        return ids[0]
    return None


def canonicalize_url(url: str) -> str:
    """Lowercase host (dropping a leading www.), strip tracking params, drop
    trailing slash and fragment -- so www/non-www and tracked/untracked links
    to the same posting produce the same dedupe key. LinkedIn and Jobstreet
    selected search results share the posting's standard direct URL."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    linkedin_host = _is_linkedin_host((parsed.hostname or "").lower())
    jobstreet_host = _jobstreet_host((parsed.hostname or "").lower())
    specialized_host = linkedin_host or bool(jobstreet_host)

    if (
        parsed.scheme.lower() in {"http", "https"}
        and linkedin_host
        and not parsed.params
        and (job_id := _linkedin_job_id(parsed.path, parsed.query))
    ):
        return f"https://linkedin.com/jobs/view/{job_id}"

    if (
        parsed.scheme.lower() in {"http", "https"}
        and jobstreet_host
        and not parsed.params
        and (job_id := _jobstreet_job_id(parsed.path, parsed.query))
    ):
        return f"https://{jobstreet_host}/job/{job_id}"

    # Invalid selected jobs must stay invalid after canonicalisation:
    # dropping a blank duplicate ID, repeated trailing slash or path parameter
    # could otherwise turn them into an apparently unambiguous posting.
    if specialized_host and parsed.path.endswith("//"):
        path = parsed.path
    kept_params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=specialized_host)
        if not _is_tracking_param(k)
    ]
    query = urlencode(sorted(kept_params))

    params = parsed.params if specialized_host else ""
    return urlunparse((parsed.scheme.lower(), host, path, params, query, ""))


def extract_source_job_id(canonical_url: str) -> str | None:
    parsed = urlparse(canonical_url)
    host = (parsed.hostname or "").lower()
    if _is_linkedin_host(host):
        if parsed.scheme.lower() not in {"http", "https"} or parsed.params:
            return None
        match = _LINKEDIN_VIEW_PATH.fullmatch(parsed.path)
        return match.group(1) if match else None
    if _jobstreet_host(host):
        if parsed.scheme.lower() not in {"http", "https"} or parsed.params:
            return None
        return _jobstreet_job_id(parsed.path, parsed.query)
    for host_fragment, pattern in _SOURCE_ID_PATTERNS:
        if host_fragment in host and (match := pattern.search(canonical_url)):
            return match.group(1)
    return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def compute_dedupe_key(
    url: str,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
) -> str:
    canonical = canonicalize_url(url)
    host = urlparse(canonical).netloc

    if source_job_id := extract_source_job_id(canonical):
        return f"srcid:{host}:{source_job_id}"
    if company and title:
        return f"ct:{_slug(company)}:{_slug(title)}:{_slug(location or '')}"
    return f"url:{canonical}"
