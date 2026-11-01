"""URL canonicalisation and dedupe key computation (docs/04_DATA_MODEL.md §7).

Pure functions, deliberately independent of the database and the ORM, so they
can be unit-tested in isolation -- this is the logic most likely to need tuning
as real captures reveal new tracking-param and source-ID patterns.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TRACKING_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid")

# Source-specific job-ID extraction. Each pattern is matched against the
# canonicalised URL; the first capturing group is the source's own job ID.
# Intentionally small and additive -- a source with no pattern here just falls
# through to the company+title key, never blocking capture (docs/04 §7).
_SOURCE_ID_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("linkedin.com", re.compile(r"/jobs/view/(\d+)")),
    ("jobstreet.", re.compile(r"/job/(\d+)")),
    ("glints.com", re.compile(r"/job/[^/]+/([a-zA-Z0-9]+)")),
]


def _is_tracking_param(key: str) -> bool:
    key_lower = key.lower()
    return any(key_lower.startswith(prefix) for prefix in _TRACKING_PARAM_PREFIXES)


def canonicalize_url(url: str) -> str:
    """Lowercase host (dropping a leading www.), strip tracking params, drop
    trailing slash and fragment -- so www/non-www and tracked/untracked links
    to the same posting produce the same dedupe key."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"

    kept_params = [(k, v) for k, v in parse_qsl(parsed.query) if not _is_tracking_param(k)]
    query = urlencode(sorted(kept_params))

    return urlunparse((parsed.scheme.lower(), host, path, "", query, ""))


def extract_source_job_id(canonical_url: str) -> str | None:
    host = urlparse(canonical_url).netloc
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
