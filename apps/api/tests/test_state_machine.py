"""Tests for the status state machine (docs/04 §6, docs/12 §3: "table-driven
over all statuses x event types; every legal transition succeeds, every
illegal one raises").

Two layers: explicit hand-written assertions against the documented table (so
a bug in the table's *content* is caught, not just a bug in how `next_status`
reads it), plus an exhaustive parametrized sweep generated from the module's
own table (so `next_status`'s branching logic can't silently diverge from the
table it's supposed to implement).
"""

from __future__ import annotations

import pytest

from oscar_api.core.errors import IllegalTransitionError
from oscar_api.modules.applications.state_machine import (
    _STATUS_PRESERVING_EVENTS,
    _TRANSITIONS,
    next_status,
)
from oscar_api.modules.jobs.models import JobStatus

ALL_EVENT_TYPES = [
    "APPLICATION_STARTED",
    "APPLICATION_SUBMITTED",
    "ASSESSMENT_RECEIVED",
    "INTERVIEW_RECEIVED",
    "INTERVIEW_COMPLETED",
    "FINAL_INTERVIEW",
    "REJECTED",
    "OFFER_RECEIVED",
    "WITHDRAWN",
]

# ── Explicit, hand-written spot checks against docs/04 §6 ───────────────────


@pytest.mark.parametrize(
    ("start", "event_type", "expected"),
    [
        (JobStatus.SAVED, "APPLICATION_SUBMITTED", JobStatus.APPLIED),
        (JobStatus.READY_TO_APPLY, "APPLICATION_SUBMITTED", JobStatus.APPLIED),
        (JobStatus.APPLYING, "APPLICATION_SUBMITTED", JobStatus.APPLIED),
        (JobStatus.APPLIED, "ASSESSMENT_RECEIVED", JobStatus.ASSESSMENT),
        (JobStatus.APPLIED, "INTERVIEW_RECEIVED", JobStatus.INTERVIEW),
        (JobStatus.APPLIED, "REJECTED", JobStatus.REJECTED),
        (JobStatus.APPLIED, "OFFER_RECEIVED", JobStatus.OFFER),
        (JobStatus.APPLIED, "WITHDRAWN", JobStatus.WITHDRAWN),
        (JobStatus.ASSESSMENT, "INTERVIEW_RECEIVED", JobStatus.INTERVIEW),
        (JobStatus.ASSESSMENT, "REJECTED", JobStatus.REJECTED),
        (JobStatus.INTERVIEW, "INTERVIEW_RECEIVED", JobStatus.INTERVIEW),  # 2nd round
        (JobStatus.INTERVIEW, "FINAL_INTERVIEW", JobStatus.FINAL_INTERVIEW),
        (JobStatus.INTERVIEW, "OFFER_RECEIVED", JobStatus.OFFER),
        (JobStatus.FINAL_INTERVIEW, "OFFER_RECEIVED", JobStatus.OFFER),
        (JobStatus.FINAL_INTERVIEW, "REJECTED", JobStatus.REJECTED),
        (JobStatus.OFFER, "WITHDRAWN", JobStatus.WITHDRAWN),
    ],
)
def test_documented_legal_transitions(start, event_type, expected) -> None:
    assert next_status(start, event_type) == expected


@pytest.mark.parametrize(
    ("start", "event_type"),
    [
        (JobStatus.REJECTED, "OFFER_RECEIVED"),  # terminal
        (JobStatus.WITHDRAWN, "APPLICATION_SUBMITTED"),  # terminal
        (JobStatus.OFFER, "REJECTED"),  # offer only goes to withdrawn
        (JobStatus.APPLIED, "FINAL_INTERVIEW"),  # can't skip straight to final
        (JobStatus.SAVED, "OFFER_RECEIVED"),  # can't jump the whole funnel
    ],
)
def test_documented_illegal_transitions_are_rejected(start, event_type) -> None:
    with pytest.raises(IllegalTransitionError):
        next_status(start, event_type)


def test_interview_completed_is_informational_and_does_not_change_status() -> None:
    assert next_status(JobStatus.INTERVIEW, "INTERVIEW_COMPLETED") == JobStatus.INTERVIEW
    assert (
        next_status(JobStatus.FINAL_INTERVIEW, "INTERVIEW_COMPLETED") == JobStatus.FINAL_INTERVIEW
    )


def test_interview_completed_before_an_interview_is_illegal() -> None:
    with pytest.raises(IllegalTransitionError):
        next_status(JobStatus.APPLIED, "INTERVIEW_COMPLETED")


def test_illegal_transition_error_carries_useful_detail() -> None:
    with pytest.raises(IllegalTransitionError) as exc_info:
        next_status(JobStatus.REJECTED, "OFFER_RECEIVED")
    assert exc_info.value.detail == {"from": "REJECTED", "event_type": "OFFER_RECEIVED"}


# ── Exhaustive sweep: every (status, event_type) pair, generated from the
# module's own table -- catches `next_status` control-flow bugs even where no
# hand-written case above happens to cover that exact pair.


@pytest.mark.parametrize("status", list(JobStatus))
@pytest.mark.parametrize("event_type", ALL_EVENT_TYPES)
def test_every_pair_matches_the_implementations_own_table(status, event_type) -> None:
    if event_type in _STATUS_PRESERVING_EVENTS:
        if status in _STATUS_PRESERVING_EVENTS[event_type]:
            assert next_status(status, event_type) == status
        else:
            with pytest.raises(IllegalTransitionError):
                next_status(status, event_type)
        return

    allowed = _TRANSITIONS.get(status, {})
    if event_type in allowed:
        assert next_status(status, event_type) == allowed[event_type]
    else:
        with pytest.raises(IllegalTransitionError):
            next_status(status, event_type)
