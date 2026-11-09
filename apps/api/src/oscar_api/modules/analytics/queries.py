"""Analytics formulas (docs/10_ANALYTICS_DEFINITIONS.md), implemented once,
here, in SQL against `v_job_stages`/`v_job_timeline` -- the dashboard and the
per-metric endpoints both call these functions, so the two can never disagree
about what a number means (docs/10 §1: "one vocabulary, one implementation").

V1 queries Postgres directly (master spec §12) -- no warehouse, no snapshot
table. At single-user scale this is fast enough that there's no reason to
build one speculatively.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from oscar_api.config import get_settings
from oscar_api.modules.analytics.schemas import ProductivityOut

_KPI_SQL = text("""
    SELECT
      count(*) FILTER (WHERE saved_at >= :win_from AND saved_at < :win_to) AS saved,
      count(*) FILTER (
        WHERE cv_ready_at IS NOT NULL AND applied_at IS NULL
          AND current_status = 'READY_TO_APPLY'
      ) AS ready_to_apply,
      count(*) FILTER (WHERE applied_at >= :win_from AND applied_at < :win_to) AS applied,
      count(*) FILTER (WHERE assessment_at >= :win_from AND assessment_at < :win_to) AS assessment,
      count(*) FILTER (WHERE interview_at >= :win_from AND interview_at < :win_to) AS interview,
      count(*) FILTER (WHERE final_at >= :win_from AND final_at < :win_to) AS final_interview,
      count(*) FILTER (WHERE offer_at >= :win_from AND offer_at < :win_to) AS offer,
      count(*) FILTER (WHERE rejected_at >= :win_from AND rejected_at < :win_to) AS rejected
    FROM v_job_stages
""")

_FUNNEL_SQL = text("""
    SELECT
      count(*) FILTER (WHERE saved_at IS NOT NULL AND current_status <> 'SKIPPED') AS stage_saved,
      count(*) FILTER (WHERE applied_at IS NOT NULL)    AS stage_applied,
      count(*) FILTER (WHERE assessment_at IS NOT NULL) AS stage_assessment,
      count(*) FILTER (WHERE interview_at IS NOT NULL)  AS stage_interview,
      count(*) FILTER (WHERE final_at IS NOT NULL)       AS stage_final,
      count(*) FILTER (WHERE offer_at IS NOT NULL)       AS stage_offer
    FROM v_job_stages
""")

# D3: SKIPPED is excluded from the saved denominator (a good triage decision
# shouldn't depress conversion); D5: interview conversion counts distinct
# jobs reaching a stage, never events -- a 3-round interview is one job.
_CONVERSION_SQL = text("""
    WITH s AS (SELECT * FROM v_job_stages),
    saved_eligible AS (
      SELECT count(*) AS n FROM s WHERE saved_at IS NOT NULL AND current_status <> 'SKIPPED'
    ),
    reached AS (
      SELECT
        count(*) FILTER (WHERE applied_at IS NOT NULL)    AS applied,
        count(*) FILTER (WHERE assessment_at IS NOT NULL) AS assessment,
        count(*) FILTER (WHERE interview_at IS NOT NULL)  AS interview,
        count(*) FILTER (WHERE offer_at IS NOT NULL)      AS offer
      FROM s
    )
    SELECT
      reached.applied::numeric / nullif(saved_eligible.n, 0)      AS applied_over_saved,
      reached.assessment::numeric / nullif(reached.applied, 0)    AS assessment_over_applied,
      reached.interview::numeric / nullif(reached.applied, 0)     AS interview_over_applied,
      reached.offer::numeric / nullif(reached.interview, 0)       AS offer_over_interview,
      reached.offer::numeric / nullif(reached.applied, 0)         AS offer_over_applied
    FROM reached, saved_eligible
""")

_BACKLOG_SQL = text("""
    SELECT
      count(*) FILTER (
        WHERE cv_ready_at IS NOT NULL AND applied_at IS NULL
          AND current_status = 'READY_TO_APPLY'
      ) AS cv_ready_not_applied,
      count(*) FILTER (
        WHERE current_status = 'SAVED' AND job_id IN (
          SELECT id FROM jobs WHERE created_at < now() - interval '5 days'
        )
      ) AS saved_older_than_5d,
      count(*) FILTER (
        WHERE current_status IN ('SAVED', 'READY_TO_APPLY') AND NOT EXISTS (
          SELECT 1 FROM cv_versions WHERE cv_versions.job_id = v_job_stages.job_id
        )
      ) AS jobs_without_cv,
      count(*) FILTER (
        WHERE current_status IN ('ASSESSMENT', 'INTERVIEW', 'FINAL_INTERVIEW')
          AND job_id NOT IN (
            SELECT job_id FROM v_job_timeline
            GROUP BY job_id HAVING max(occurred_at) >= now() - interval '7 days'
          )
      ) AS applications_needing_action
    FROM v_job_stages
""")

_PARTIAL_CAPTURES_SQL = text("""
    SELECT count(*) AS n FROM jobs
    WHERE capture_completeness != 'CAPTURED_COMPLETE' AND duplicate_of_job_id IS NULL
""")

_TRENDS_SQL = text("""
    WITH buckets AS (
      SELECT generate_series(
        date_trunc(:granularity, (:win_from AT TIME ZONE :tz)),
        date_trunc(:granularity, (now() AT TIME ZONE :tz)),
        CAST(:step AS interval)
      ) AS bucket
    ),
    saved AS (
      SELECT date_trunc(:granularity, (saved_at AT TIME ZONE :tz)) AS bucket, count(*) AS n
      FROM v_job_stages WHERE saved_at >= :win_from GROUP BY 1
    ),
    applied AS (
      SELECT date_trunc(:granularity, (applied_at AT TIME ZONE :tz)) AS bucket, count(*) AS n
      FROM v_job_stages WHERE applied_at >= :win_from GROUP BY 1
    ),
    interviews AS (
      SELECT date_trunc(:granularity, (interview_at AT TIME ZONE :tz)) AS bucket, count(*) AS n
      FROM v_job_stages WHERE interview_at >= :win_from GROUP BY 1
    ),
    offers AS (
      SELECT date_trunc(:granularity, (offer_at AT TIME ZONE :tz)) AS bucket, count(*) AS n
      FROM v_job_stages WHERE offer_at >= :win_from GROUP BY 1
    )
    SELECT b.bucket,
           coalesce(s.n, 0) AS saved,
           coalesce(a.n, 0) AS applied,
           coalesce(i.n, 0) AS interviews,
           coalesce(o.n, 0) AS offers
    FROM buckets b
    LEFT JOIN saved s ON s.bucket = b.bucket
    LEFT JOIN applied a ON a.bucket = b.bucket
    LEFT JOIN interviews i ON i.bucket = b.bucket
    LEFT JOIN offers o ON o.bucket = b.bucket
    ORDER BY b.bucket
""")

_SOURCE_SQL = text("""
    SELECT coalesce(s.name, 'unknown') AS name,
           count(*) AS saved,
           count(*) FILTER (WHERE js.applied_at IS NOT NULL)   AS applied,
           count(*) FILTER (WHERE js.interview_at IS NOT NULL) AS interview,
           (count(*) FILTER (WHERE js.applied_at IS NOT NULL))::numeric
             / nullif(count(*), 0) AS applied_rate
    FROM v_job_stages js
    LEFT JOIN sources s ON s.id = js.source_id
    GROUP BY 1 ORDER BY saved DESC
""")

_ROLE_SQL = text("""
    SELECT coalesce(r.name, 'unclassified') AS name,
           count(*) AS saved,
           count(*) FILTER (WHERE js.applied_at IS NOT NULL)   AS applied,
           count(*) FILTER (WHERE js.interview_at IS NOT NULL) AS interview,
           (count(*) FILTER (WHERE js.applied_at IS NOT NULL))::numeric
             / nullif(count(*), 0) AS applied_rate
    FROM v_job_stages js
    LEFT JOIN role_categories r ON r.id = js.role_category_id
    GROUP BY 1 ORDER BY saved DESC
""")

_PRODUCTIVITY_SQL = text("""
    SELECT
      percentile_cont(0.5) WITHIN GROUP (
        ORDER BY extract(epoch FROM (cv_ready_at - saved_at)) / 86400.0
      ) FILTER (WHERE cv_ready_at IS NOT NULL) AS median_saved_to_cv_ready_days,
      percentile_cont(0.5) WITHIN GROUP (
        ORDER BY extract(epoch FROM (applied_at - saved_at)) / 86400.0
      ) FILTER (WHERE applied_at IS NOT NULL) AS median_saved_to_applied_days,
      count(*) FILTER (WHERE applied_at >= now() - interval '7 days') AS applications_last_7d,
      count(*) FILTER (
        WHERE cv_ready_at IS NOT NULL AND applied_at IS NULL
          AND current_status = 'READY_TO_APPLY'
      ) AS backlog_size
    FROM v_job_stages
""")


def _default_window(days: int) -> tuple[dt.datetime, dt.datetime]:
    now = dt.datetime.now(dt.UTC)
    return now - dt.timedelta(days=days), now


def get_kpis(session: Session, *, window_days: int = 30) -> dict[str, int]:
    win_from, win_to = _default_window(window_days)
    row = session.execute(_KPI_SQL, {"win_from": win_from, "win_to": win_to}).mappings().one()
    return dict(row)


def get_funnel(session: Session) -> list[dict[str, Any]]:
    row = session.execute(_FUNNEL_SQL).mappings().one()
    return [
        {"stage": "SAVED", "count": row["stage_saved"]},
        {"stage": "APPLIED", "count": row["stage_applied"]},
        {"stage": "ASSESSMENT", "count": row["stage_assessment"]},
        {"stage": "INTERVIEW", "count": row["stage_interview"]},
        {"stage": "FINAL_INTERVIEW", "count": row["stage_final"]},
        {"stage": "OFFER", "count": row["stage_offer"]},
    ]


def get_conversion(session: Session) -> dict[str, float | None]:
    row = session.execute(_CONVERSION_SQL).mappings().one()
    return {k: (float(v) if v is not None else None) for k, v in row.items()}


def get_backlog(session: Session) -> dict[str, int]:
    row = dict(session.execute(_BACKLOG_SQL).mappings().one())
    row["partial_captures"] = session.execute(_PARTIAL_CAPTURES_SQL).scalar_one()
    return row


def get_action_queue(session: Session) -> list[dict[str, Any]]:
    backlog = get_backlog(session)
    items = [
        (
            "CV ready but not applied",
            backlog["cv_ready_not_applied"],
            "/jobs?status=READY_TO_APPLY",
        ),
        (
            "Saved more than 5 days ago",
            backlog["saved_older_than_5d"],
            "/jobs?status=SAVED&older_than=5d",
        ),
        ("Jobs without a generated CV", backlog["jobs_without_cv"], "/jobs?missing_cv=1"),
        (
            "Applications needing a follow-up",
            backlog["applications_needing_action"],
            "/jobs?needs_action=1",
        ),
        (
            "Partial captures needing enrichment",
            backlog["partial_captures"],
            "/jobs?needs_description=1",
        ),
    ]
    return [
        {"label": label, "count": count, "href": href + "&exclude_duplicates=1"}
        for label, count, href in items
        if count > 0
    ]


def get_trends(
    session: Session, *, granularity: str = "week", window_days: int = 90
) -> list[dict[str, Any]]:
    if granularity not in ("week", "month"):
        raise ValueError("granularity must be 'week' or 'month'")
    step = "1 week" if granularity == "week" else "1 month"
    win_from, _ = _default_window(window_days)
    rows = (
        session.execute(
            _TRENDS_SQL,
            {
                "granularity": granularity,
                "win_from": win_from,
                "step": step,
                "tz": get_settings().timezone,
            },
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def get_source_analytics(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(_SOURCE_SQL).mappings().all()
    return [
        {
            **dict(r),
            "applied_rate": float(r["applied_rate"]) if r["applied_rate"] is not None else None,
        }
        for r in rows
    ]


def get_role_analytics(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(_ROLE_SQL).mappings().all()
    return [
        {
            **dict(r),
            "applied_rate": float(r["applied_rate"]) if r["applied_rate"] is not None else None,
        }
        for r in rows
    ]


def get_productivity(session: Session) -> ProductivityOut:
    row = session.execute(_PRODUCTIVITY_SQL).mappings().one()
    return ProductivityOut(
        median_saved_to_cv_ready_days=(
            float(row["median_saved_to_cv_ready_days"])
            if row["median_saved_to_cv_ready_days"] is not None
            else None
        ),
        median_saved_to_applied_days=(
            float(row["median_saved_to_applied_days"])
            if row["median_saved_to_applied_days"] is not None
            else None
        ),
        applications_last_7d=row["applications_last_7d"],
        backlog_size=row["backlog_size"],
    )


# docs/10 §9: deliberately not computed. "Time saved" needs a manual baseline
# assumption the system cannot observe -- publishing a fabricated efficiency
# number in a product whose core promise is factual honesty (G3) would be
# self-undermining. The north-star metric itself needs deliberate manual
# timing during M6, not an automatic query.
