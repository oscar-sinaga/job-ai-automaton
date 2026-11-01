# 10 — Analytics Definitions

Master spec §41 rates *"analytics misleading"* as a **high-impact** risk, and its mitigation is exactly this document: every number the dashboard shows has one written definition and one implementation. All metrics live in `modules/analytics/queries.py`; no metric is computed anywhere else.

Standing UI disclosure (FR-010): **analytics describe the user's captured-job sample, not the job market.**

---

## 1. Foundational Semantic Decisions

These four decisions determine whether the numbers mean anything. They are stated first because every formula below depends on them.

### D1 — Counts are *stage-reached*, not *current status*

A job now `REJECTED` still reached `INTERVIEW`. Funnel and KPI counts therefore use **"ever reached this stage", derived from events**, not `jobs.current_status`. Using current status would make the funnel shrink as processes conclude, which is the single most common way a job-search dashboard lies to its owner.

The dashboard shows a separate, clearly labelled *current status* breakdown for "where things stand right now". The two are different questions and are never mixed in one chart.

### D2 — Duplicates are excluded

Any job with `duplicate_of_job_id IS NOT NULL` is excluded from every metric. It remains in the database and in the inbox (flagged) — it just never counts twice.

### D3 — `SKIPPED` and `WITHDRAWN` treatment

| Status | Counted in saved? | In applied→X denominators? | Rationale |
|---|---|---|---|
| `SKIPPED` (decided not to apply) | Yes, in the captured sample | **No** — excluded from `eligible_saved` | Deliberately not applying is a good decision; penalising it in conversion would make the metric argue against triage |
| `WITHDRAWN` (applied, then pulled out) | Yes | **Yes** — it did reach `APPLIED` | The application happened; removing it would inflate downstream conversion |

### D4 — Conversion is all-time by default; windowed conversion is cohort-truncated

A job saved yesterday has not had time to become an interview. So:

- **Counts and trends** are windowed by event date (`window=30d` → events in the last 30 days).
- **Conversion ratios default to all-time.** When a window is applied, the cohort is *jobs whose entry event falls in the window*, and the response is tagged `"cohort_immature": true` when the window ends within 21 days of now — the UI must show that caveat rather than let a 4% conversion rate read as failure when it is really recency.

---

## 2. Base Views

Every metric derives from these two views, so the semantics above are enforced once rather than re-implemented per query.

```sql
-- All lifecycle events for a job, from both event tables, in one stream.
create view v_job_timeline as
  select job_id, event_type, occurred_at from job_events
  union all
  select a.job_id, ae.event_type, ae.occurred_at
    from application_events ae
    join applications a on a.id = ae.application_id;

-- First time each job reached each stage. Duplicates excluded (D2).
create view v_job_stages as
  select
    j.id                                                                        as job_id,
    j.source_id, j.role_category_id, j.current_status,
    min(t.occurred_at) filter (where t.event_type = 'JOB_SAVED')               as saved_at,
    min(t.occurred_at) filter (where t.event_type = 'CV_GENERATED')            as cv_generated_at,
    min(t.occurred_at) filter (where t.event_type = 'CV_APPROVED')             as cv_ready_at,
    min(t.occurred_at) filter (where t.event_type = 'APPLICATION_SUBMITTED')   as applied_at,
    min(t.occurred_at) filter (where t.event_type = 'ASSESSMENT_RECEIVED')     as assessment_at,
    min(t.occurred_at) filter (where t.event_type = 'INTERVIEW_RECEIVED')      as interview_at,
    min(t.occurred_at) filter (where t.event_type = 'FINAL_INTERVIEW')         as final_at,
    min(t.occurred_at) filter (where t.event_type = 'OFFER_RECEIVED')          as offer_at,
    min(t.occurred_at) filter (where t.event_type = 'REJECTED')                as rejected_at,
    max(t.occurred_at) filter (where t.event_type = 'INTERVIEW_RECEIVED')      as last_interview_at,
    count(*)           filter (where t.event_type = 'INTERVIEW_RECEIVED')      as interview_rounds
  from jobs j
  left join v_job_timeline t on t.job_id = j.id
  where j.duplicate_of_job_id is null
  group by j.id;
```

`min(...)` is what implements D1: the *first* time a stage was reached, regardless of what happened afterwards. `interview_rounds` exists so multi-round processes are visible without being double-counted in the funnel (D5 below).

---

## 3. KPI Counts

```sql
-- window: [:from, :to) on the stage's own timestamp
select
  count(*) filter (where saved_at      >= :from and saved_at      < :to) as saved,
  count(*) filter (where cv_ready_at   is not null and applied_at is null) as ready_to_apply,
  count(*) filter (where applied_at    >= :from and applied_at    < :to) as applied,
  count(*) filter (where assessment_at >= :from and assessment_at < :to) as assessment,
  count(*) filter (where interview_at  >= :from and interview_at  < :to) as interview,
  count(*) filter (where final_at      >= :from and final_at      < :to) as final_interview,
  count(*) filter (where offer_at      >= :from and offer_at      < :to) as offer,
  count(*) filter (where rejected_at   >= :from and rejected_at   < :to) as rejected
from v_job_stages;
```

`ready_to_apply` is intentionally **not** windowed: it is a backlog state ("CV ready, not yet applied"), and a backlog is by nature current, not periodic.

---

## 4. Funnel

```text
Saved  →  Applied  →  Assessment  →  Interview  →  Final Interview  →  Offer
```

```sql
select
  count(*) filter (where saved_at      is not null and current_status <> 'SKIPPED') as stage_saved,
  count(*) filter (where applied_at    is not null)                                  as stage_applied,
  count(*) filter (where assessment_at is not null)                                  as stage_assessment,
  count(*) filter (where interview_at  is not null)                                  as stage_interview,
  count(*) filter (where final_at      is not null)                                  as stage_final,
  count(*) filter (where offer_at      is not null)                                  as stage_offer
from v_job_stages;
```

**The funnel is not strictly monotonic, and that is correct.** Assessment is optional — a job can go `APPLIED → INTERVIEW` without an assessment, so `stage_interview` may exceed `stage_assessment`. The UI must render the funnel as independent stage counts, not as a shape that implies each stage is a subset of the one above it. Forcing monotonicity here would require faking data.

---

## 5. Conversion Ratios

All denominators exclude duplicates (D2); `eligible_saved` additionally excludes `SKIPPED` (D3).

```sql
with s as (select * from v_job_stages)
select
  (select count(*) from s where applied_at    is not null)::numeric
    / nullif((select count(*) from s where saved_at is not null
                                       and current_status <> 'SKIPPED'), 0) as applied_over_saved,
  (select count(*) from s where assessment_at is not null)::numeric
    / nullif((select count(*) from s where applied_at is not null), 0)       as assessment_over_applied,
  (select count(*) from s where interview_at  is not null)::numeric
    / nullif((select count(*) from s where applied_at is not null), 0)       as interview_over_applied,
  (select count(*) from s where offer_at      is not null)::numeric
    / nullif((select count(*) from s where interview_at is not null), 0)     as offer_over_interview,
  (select count(*) from s where offer_at      is not null)::numeric
    / nullif((select count(*) from s where applied_at is not null), 0)       as offer_over_applied;
```

`nullif(..., 0)` makes an empty denominator return `NULL`, which the API serialises as `null` and the UI renders as "—". A zero-denominator ratio is undefined, never `0` — showing 0% conversion when nothing has been applied to yet is a lie.

**D5 — multi-interview:** every interview metric counts **distinct jobs** that reached interview, never interview events. A three-round process is one job at `stage_interview`, with `interview_rounds = 3` available separately. Counting events here would inflate `interview_over_applied` above 100%.

---

## 6. Backlog (drives the Action Queue, FR-011)

| Item | Definition | Link target |
|---|---|---|
`cv_ready_not_applied` | `cv_ready_at is not null and applied_at is null` | `/jobs?status=READY_TO_APPLY`
`saved_older_than_5d` | `current_status = 'SAVED' and saved_at < now() - interval '5 days'` | `/jobs?status=SAVED&older_than=5d`
`jobs_without_cv` | `cv_generated_at is null and current_status in ('SAVED','READY_TO_APPLY')` | `/jobs?missing_cv=1`
`applications_needing_action` | `current_status in ('ASSESSMENT','INTERVIEW','FINAL_INTERVIEW')` and no event in 7 days | `/jobs?needs_action=1`
`partial_captures` | `capture_completeness = 'CAPTURED_PARTIAL'` | `/jobs?completeness=CAPTURED_PARTIAL`

Each count and its link must return the same set — a mismatch is a bug, and [12_TEST_STRATEGY](12_TEST_STRATEGY.md) requires a test asserting count == length(linked result) for every row here.

`partial_captures` is added beyond the master spec's list because unenriched mobile captures are the backlog item most likely to rot invisibly ([09_MOBILE_CAPTURE_DESIGN](09_MOBILE_CAPTURE_DESIGN.md) §4).

---

## 7. Trends

Weekly (or monthly) series, bucketed by the stage's own event date:

```sql
select date_trunc(:granularity, saved_at) as bucket,
       count(*) filter (where saved_at   is not null) as saved,
       count(*) filter (where applied_at is not null) as applied
from v_job_stages
where saved_at >= :from
group by 1 order by 1;
```

Interviews and offers use the same shape on `interview_at` / `offer_at`. Buckets use the **local timezone (`Asia/Jakarta`)**, not UTC — a job saved at 06:00 WIB belongs to that day as the user experienced it, and a UTC-bucketed week boundary would silently shift counts between weeks.

Empty buckets are emitted as zeros (via `generate_series`) so a gap reads as "no activity" rather than as a missing week.

---

## 8. Role, Source, and Skill Analytics

**Role** (`role_categories`) and **source** (`sources`) share one shape:

```sql
select coalesce(s.name, 'unknown') as source, 
       count(*)                                             as saved,
       count(*) filter (where js.applied_at   is not null)   as applied,
       count(*) filter (where js.interview_at is not null)   as interview,
       count(*) filter (where js.applied_at   is not null)::numeric
         / nullif(count(*), 0)                               as applied_rate
from v_job_stages js
left join sources s on s.id = js.source_id
group by 1 order by saved desc;
```

**Skills** come from `job_skills` (parser output plus manual corrections) and answer three questions:

```sql
-- top skills demanded across captured jobs
select skill_name, count(distinct job_id) as jobs, kind
from job_skills group by 1, 3 order by jobs desc limit :top;

-- skill gap: demanded by jobs, absent from the career profile
select js.skill_name, count(distinct js.job_id) as demanded_by
from job_skills js
where not exists (
  select 1 from career_skills cs
  where lower(cs.name) = lower(js.skill_name))
group by 1 order by demanded_by desc;
```

The skill-gap query is the most directly actionable number in the product — it says what to learn next — and it is only as good as `job_skills`, which is parser output. Its accuracy is therefore bounded by parser quality (P1), and the UI must label it as derived from automatic extraction.

Source/role counts inherit any classification gaps: unclassified rows appear as `'unknown'` rather than being dropped, so totals always reconcile with the KPI counts.

---

## 9. Productivity

```sql
select
  percentile_cont(0.5) within group (order by cv_ready_at - saved_at)
    filter (where cv_ready_at is not null)                        as median_saved_to_cv_ready,
  percentile_cont(0.5) within group (order by applied_at - saved_at)
    filter (where applied_at is not null)                         as median_saved_to_applied,
  count(*) filter (where applied_at >= now() - interval '7 days') as applications_last_7d,
  count(*) filter (where cv_ready_at is not null and applied_at is null) as backlog_size
from v_job_stages;
```

Medians, not means: a single job left sitting for three months would drag a mean beyond usefulness.

**Not computed automatically: "estimated time saved."** The master spec lists it as optional ("if feasible"), and it would require a manual-baseline assumption that the system cannot observe. Publishing a fabricated efficiency number in a product whose core promise is factual honesty would be self-undermining. If wanted, it is shown as an explicit user-configurable estimate (`baseline_minutes_per_application × applications`), labelled as an assumption. The north-star metric itself (human active minutes per application) is **not** derivable from stored events either — it needs deliberate manual timing during stabilization ([15_ROADMAP_AND_MILESTONES](15_ROADMAP_AND_MILESTONES.md) M6).

---

## 10. Verification

The funnel and backlog numbers are correct only if they are *tested*, not merely defined. [12_TEST_STRATEGY](12_TEST_STRATEGY.md) requires a fixture dataset with hand-counted expected values for every formula in this document, including the deliberately awkward cases: a skipped job, a withdrawn application, a duplicate pair, a job that reached interview then was rejected, a three-round interview, and a job that went `APPLIED → INTERVIEW` with no assessment.
