"""Exercise the Docker simulation pilot, including PDF and restart persistence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--verify-state", action="store_true")
    args = parser.parse_args()
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.simulation").read_text().splitlines()
        if line and not line.startswith("#")
    )
    key = values["OSCAR_API_KEY"]

    def call(path: str, method: str = "GET", body: object = None) -> dict:
        payload = json.dumps(body).encode() if body is not None else None
        request = Request(
            API + path,
            data=payload,
            method=method,
            headers={"X-API-Key": key, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    assert call("/health")["env"] == "simulation", (
        "Refuse to mutate a non-simulation API"
    )
    assert call("/health")["db"] == "ok"
    with urlopen("http://127.0.0.1:5173/jobs", timeout=30) as response:
        html = response.read().decode()
    assert "Simulation mode" in html
    assert key not in html, "Server API key must not appear in browser HTML"
    try:
        urlopen(API + "/api/v1/jobs", timeout=30)
        raise AssertionError("API accepted an unauthenticated request")
    except HTTPError as error:
        assert error.code == 401

    if args.verify_state:
        saved = json.loads(args.state.read_text())
        job = call(f"/api/v1/jobs/{saved['job_id']}")
        assert job["current_status"] == "INTERVIEW"
        request = Request(API + saved["download_url"], headers={"X-API-Key": key})
        with urlopen(request, timeout=30) as response:
            assert hashlib.sha256(response.read()).hexdigest() == saved["pdf_sha256"]
        assert call(f"/api/v1/cv/{saved['cv_id']}")["is_approved"]
        print(
            "PASS: job, approved CV, tracking and identical PDF survive container recreation"
        )
        return

    job = call(
        "/api/v1/jobs/capture",
        "POST",
        {
            "url": "https://example.com/pilot-smoke",
            "page_title": "Just a moment...",
            "raw_text": "Performing security verification. Performance and Security by Cloudflare.",
            "capture_method": "extension",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    )
    assert job["capture_completeness"] == "NEEDS_ENRICHMENT"
    job_id = job["job_id"]
    call(
        f"/api/v1/jobs/{job_id}/snapshots",
        "POST",
        {
            "raw_text": "Example Data Engineer vacancy. Build Python and SQL data pipelines and reporting.",
            "capture_method": "paste_text",
            "captured_at": dt.datetime.now(dt.UTC).isoformat(),
        },
    )
    experience = call(
        "/api/v1/career-profile/experiences",
        "POST",
        {
            "company": "Example Pilot Company",
            "title": "Data Engineer",
            "start_date": "2022-01-01",
            "is_current": True,
        },
    )
    call(
        "/api/v1/career-profile/achievements",
        "POST",
        {
            "statement": "Built Python and SQL data pipelines for example warehouse reports.",
            "experience_id": experience["id"],
            "skill_tags": ["Python", "SQL"],
        },
    )
    call(
        "/api/v1/career-profile/application-profile",
        "PATCH",
        {
            "links": {
                "cv_name": "Example Pilot Candidate",
                "cv_email": "pilot@example.com",
            },
        },
    )
    generated = call(f"/api/v1/jobs/{job_id}/generate-cv", "POST", {})
    assert generated["run"]["model_name"] == "simulation-no-api"
    cv_id = generated["cv_version_id"]
    call(f"/api/v1/cv/{cv_id}/approve", "POST")
    exported = call(f"/api/v1/cv/{cv_id}/export", "POST")
    request = Request(API + exported["download_url"], headers={"X-API-Key": key})
    with urlopen(request, timeout=30) as response:
        pdf = response.read()
    assert pdf.startswith(b"%PDF")
    application = call(
        "/api/v1/applications",
        "POST",
        {
            "job_id": job_id,
            "submitted_cv_version_id": cv_id,
        },
    )
    call(
        f"/api/v1/applications/{application['id']}/events",
        "POST",
        {
            "event_type": "INTERVIEW_RECEIVED",
        },
    )
    assert call("/api/v1/dashboard")
    args.state.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "cv_id": cv_id,
                "download_url": exported["download_url"],
                "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
            },
            indent=2,
        )
    )
    print(
        "PASS: authenticated capture, enrichment, profile, simulated CV, approval, PDF and tracking"
    )


if __name__ == "__main__":
    main()
