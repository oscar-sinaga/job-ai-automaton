"""OSCAR Job Copilot API.

Milestone 0 exposes only ``/health``. Feature routers arrive from M1 onward --
see docs/05_API_DESIGN.md for the full planned surface and docs/15 for sequencing.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from oscar_api.config import get_settings
from oscar_api.core.errors import register_error_handlers
from oscar_api.db import check_database
from oscar_api.modules.analytics.router import dashboard_router
from oscar_api.modules.analytics.router import router as analytics_router
from oscar_api.modules.applications.router import jobs_router as applications_jobs_router
from oscar_api.modules.applications.router import router as applications_router
from oscar_api.modules.career.router import router as career_router
from oscar_api.modules.cv.router import cv_router
from oscar_api.modules.cv.router import jobs_router as cv_jobs_router
from oscar_api.modules.jobs.router import router as jobs_router

settings = get_settings()

app = FastAPI(
    title="OSCAR Job Copilot API",
    version=settings.version,
    description="Personal job-search operating system. See docs/ for the design pack.",
)

register_error_handlers(app)
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(career_router, prefix="/api/v1")
app.include_router(cv_jobs_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(applications_jobs_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(cv_router, prefix="/api/v1")

# Explicit allowlist, never "*": any site the user visits could otherwise POST
# to this local API (docs/11 §3).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Idempotency-Key"],
)


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    db: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Report service state.

    Deliberately returns 200 even when the database is unreachable: the endpoint's
    job is to *report* state, and a probe that fails because a dependency is down
    makes diagnosis harder rather than easier (docs/05 §2).
    """
    return HealthResponse(
        status="ok",
        version=settings.version,
        env=settings.env,
        db="ok" if check_database() else "unavailable",
    )
