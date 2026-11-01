"""HTTP surface for the analytics module (docs/05_API_DESIGN.md §8).

Two routers: `dashboard_router` for the single `/dashboard` endpoint (no
`/analytics` prefix, matching docs/05), and `router` for the per-metric
endpoints under `/analytics`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from oscar_api.core.auth import require_api_key
from oscar_api.db import get_session
from oscar_api.modules.analytics import queries
from oscar_api.modules.analytics.schemas import (
    SAMPLE_NOTE,
    ActionQueueItem,
    Backlog,
    Conversion,
    DashboardOut,
    FunnelStage,
    KPIs,
    ProductivityOut,
    RoleStat,
    SkillAnalyticsOut,
    SourceStat,
    TrendPoint,
)

dashboard_router = APIRouter(tags=["analytics"], dependencies=[Depends(require_api_key)])
router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_api_key)])


@dashboard_router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    window_days: int = Query(default=30, ge=1, le=365), session: Session = Depends(get_session)
) -> DashboardOut:
    return DashboardOut(
        kpis=KPIs(**queries.get_kpis(session, window_days=window_days)),
        funnel=[FunnelStage(**s) for s in queries.get_funnel(session)],
        conversion=Conversion(**queries.get_conversion(session)),
        backlog=Backlog(**queries.get_backlog(session)),
        action_queue=[ActionQueueItem(**item) for item in queries.get_action_queue(session)],
        sample_note=SAMPLE_NOTE,
    )


@router.get("/funnel", response_model=list[FunnelStage])
def get_funnel(session: Session = Depends(get_session)) -> list[FunnelStage]:
    return [FunnelStage(**s) for s in queries.get_funnel(session)]


@router.get("/trends", response_model=list[TrendPoint])
def get_trends(
    granularity: str = Query(default="week", pattern="^(week|month)$"),
    window_days: int = Query(default=90, ge=1, le=730),
    session: Session = Depends(get_session),
) -> list[TrendPoint]:
    return [
        TrendPoint(**p)
        for p in queries.get_trends(session, granularity=granularity, window_days=window_days)
    ]


@router.get("/sources", response_model=list[SourceStat])
def get_sources(session: Session = Depends(get_session)) -> list[SourceStat]:
    return [SourceStat(**s) for s in queries.get_source_analytics(session)]


@router.get("/roles", response_model=list[RoleStat])
def get_roles(session: Session = Depends(get_session)) -> list[RoleStat]:
    return [RoleStat(**s) for s in queries.get_role_analytics(session)]


@router.get("/skills", response_model=SkillAnalyticsOut)
def get_skills() -> SkillAnalyticsOut:
    return SkillAnalyticsOut()


@router.get("/productivity", response_model=ProductivityOut)
def get_productivity(session: Session = Depends(get_session)) -> ProductivityOut:
    return queries.get_productivity(session)
