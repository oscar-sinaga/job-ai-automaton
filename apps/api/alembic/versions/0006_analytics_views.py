"""analytics: v_job_timeline, v_job_stages views

Milestone 5. Implements docs/10_ANALYTICS_DEFINITIONS.md §2 exactly: a merged
event stream across job_events + application_events, and a per-job "first
time each stage was reached" view that every KPI/funnel/conversion/trend
query builds on. Duplicates (docs/10 D2) are excluded here, once, rather than
in every downstream query.

Revision ID: 0006_analytics_views
Revises: 0005_applications
Create Date: 2026-08-28

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_analytics_views"
down_revision: str | None = "0005_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_TIMELINE = """
CREATE VIEW v_job_timeline AS
  SELECT job_id, event_type, occurred_at FROM job_events
  UNION ALL
  SELECT a.job_id, ae.event_type, ae.occurred_at
    FROM application_events ae
    JOIN applications a ON a.id = ae.application_id
"""

_CREATE_STAGES = """
CREATE VIEW v_job_stages AS
  SELECT
    j.id AS job_id,
    j.source_id, j.role_category_id, j.current_status,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'JOB_SAVED')             AS saved_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'CV_GENERATED')          AS cv_generated_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'CV_APPROVED')           AS cv_ready_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'APPLICATION_SUBMITTED') AS applied_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'ASSESSMENT_RECEIVED')   AS assessment_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'INTERVIEW_RECEIVED')    AS interview_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'FINAL_INTERVIEW')       AS final_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'OFFER_RECEIVED')        AS offer_at,
    min(t.occurred_at) FILTER (WHERE t.event_type = 'REJECTED')              AS rejected_at,
    max(t.occurred_at) FILTER (WHERE t.event_type = 'INTERVIEW_RECEIVED')    AS last_interview_at,
    count(*)           FILTER (WHERE t.event_type = 'INTERVIEW_RECEIVED')    AS interview_rounds
  FROM jobs j
  LEFT JOIN v_job_timeline t ON t.job_id = j.id
  WHERE j.duplicate_of_job_id IS NULL
  GROUP BY j.id
"""


def upgrade() -> None:
    op.execute(_CREATE_TIMELINE)
    op.execute(_CREATE_STAGES)


def downgrade() -> None:
    op.execute("DROP VIEW v_job_stages")
    op.execute("DROP VIEW v_job_timeline")
