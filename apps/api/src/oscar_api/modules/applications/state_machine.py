"""The status state machine (docs/04_DATA_MODEL.md §6).

`jobs.current_status` is the sole materialized status column (ADR-005) --
there is no separate `applications.current_status`. This module is the only
place that decides whether a transition is legal; every status change in the
app goes through `next_status`, never a direct assignment.
"""

from __future__ import annotations

from oscar_api.core.errors import IllegalTransitionError
from oscar_api.modules.jobs.models import JobStatus

# docs/04 §6. Terminal states (REJECTED, WITHDRAWN, SKIPPED handled via jobs
# module for the pre-application case) have no entries -- any event applied
# to them is illegal.
_TRANSITIONS: dict[JobStatus, dict[str, JobStatus]] = {
    JobStatus.SAVED: {
        "APPLICATION_STARTED": JobStatus.APPLYING,
        "APPLICATION_SUBMITTED": JobStatus.APPLIED,
    },
    JobStatus.READY_TO_APPLY: {
        "APPLICATION_STARTED": JobStatus.APPLYING,
        "APPLICATION_SUBMITTED": JobStatus.APPLIED,
    },
    JobStatus.APPLYING: {
        "APPLICATION_SUBMITTED": JobStatus.APPLIED,
        "WITHDRAWN": JobStatus.WITHDRAWN,
    },
    JobStatus.APPLIED: {
        "ASSESSMENT_RECEIVED": JobStatus.ASSESSMENT,
        "INTERVIEW_RECEIVED": JobStatus.INTERVIEW,
        "REJECTED": JobStatus.REJECTED,
        "OFFER_RECEIVED": JobStatus.OFFER,
        "WITHDRAWN": JobStatus.WITHDRAWN,
    },
    JobStatus.ASSESSMENT: {
        "INTERVIEW_RECEIVED": JobStatus.INTERVIEW,
        "REJECTED": JobStatus.REJECTED,
        "WITHDRAWN": JobStatus.WITHDRAWN,
    },
    JobStatus.INTERVIEW: {
        # Self-loop: a second/third interview round is common and must not be
        # mistaken for a re-application (docs/10 §5, interview_rounds).
        "INTERVIEW_RECEIVED": JobStatus.INTERVIEW,
        "FINAL_INTERVIEW": JobStatus.FINAL_INTERVIEW,
        "OFFER_RECEIVED": JobStatus.OFFER,
        "REJECTED": JobStatus.REJECTED,
        "WITHDRAWN": JobStatus.WITHDRAWN,
    },
    JobStatus.FINAL_INTERVIEW: {
        "OFFER_RECEIVED": JobStatus.OFFER,
        "REJECTED": JobStatus.REJECTED,
        "WITHDRAWN": JobStatus.WITHDRAWN,
    },
    JobStatus.OFFER: {
        "WITHDRAWN": JobStatus.WITHDRAWN,
    },
}

# Informational only -- logged as an event but never changes status (no row
# in _TRANSITIONS would make sense: "an interview happened" says nothing
# about the outcome yet).
_STATUS_PRESERVING_EVENTS: dict[str, tuple[JobStatus, ...]] = {
    "INTERVIEW_COMPLETED": (JobStatus.INTERVIEW, JobStatus.FINAL_INTERVIEW),
}


def next_status(current: JobStatus, event_type: str) -> JobStatus:
    """Returns the status after applying `event_type`, or raises
    `IllegalTransitionError` (409) if the transition isn't allowed."""
    if event_type in _STATUS_PRESERVING_EVENTS:
        if current in _STATUS_PRESERVING_EVENTS[event_type]:
            return current
        raise IllegalTransitionError(
            f"Cannot record {event_type} for a job in status {current.value}",
            detail={"from": current.value, "event_type": event_type},
        )

    allowed = _TRANSITIONS.get(current, {})
    if event_type not in allowed:
        raise IllegalTransitionError(
            f"Cannot apply {event_type} to a job in status {current.value}",
            detail={"from": current.value, "event_type": event_type},
        )
    return allowed[event_type]
