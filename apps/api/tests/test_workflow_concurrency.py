"""Overlapping writers use independent PostgreSQL sessions and synthetic facts.

The regular API fixture wraps one connection in a savepoint. These cases need
committed fixture rows visible to other connections; teardown deletes only the
rows created here. The test runner must use its disposable test database.
"""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select

from fakes import FakeLLMProvider
from oscar_api.core.errors import ConflictError, IllegalTransitionError
from oscar_api.core.models import SINGLE_USER_ID
from oscar_api.db import SessionLocal
from oscar_api.modules.applications import service as applications
from oscar_api.modules.applications.models import Application, ApplicationEvent
from oscar_api.modules.career.models import CareerAchievement, CareerExperience
from oscar_api.modules.career.service import get_profile
from oscar_api.modules.cv import generator
from oscar_api.modules.cv import service as cv
from oscar_api.modules.cv.models import CVGenerationRun, CVVersion
from oscar_api.modules.cv.schemas import CVDraft, GenerateCVRequest
from oscar_api.modules.cv.sections import snapshot_sections
from oscar_api.modules.jobs.models import (
    CaptureCompleteness,
    CaptureMethod,
    Job,
    JobEvent,
    JobEventType,
    JobRawSnapshot,
    JobStatus,
)
from oscar_api.modules.jobs.service import get_job_or_404


@dataclass
class Workflow:
    job_id: int
    cv_id: int
    sections: dict[str, Any]
    draft: dict[str, Any]


@pytest.fixture
def workflow():
    with SessionLocal() as session:
        profile = get_profile(session)
        experience = CareerExperience(
            profile_id=profile.id,
            company="Synthetic Workflow Laboratory",
            title="Fixture Analyst",
            start_date=dt.date(2022, 1, 1),
            is_current=True,
        )
        session.add(experience)
        session.flush()
        fact = CareerAchievement(
            profile_id=profile.id,
            experience_id=experience.id,
            statement="Produced deterministic fixture reports.",
            skill_tags=[],
            domain_tags=[],
            technology_tags=[],
        )
        job = Job(
            user_id=SINGLE_USER_ID,
            ref="",
            url=f"https://example.test/workflow/{uuid4()}",
            capture_completeness=CaptureCompleteness.CAPTURED_COMPLETE,
            current_status=JobStatus.SAVED,
        )
        session.add_all([fact, job])
        session.flush()
        job.ref = f"J{job.id:03d}"
        session.add(
            JobRawSnapshot(
                job_id=job.id,
                raw_text="Produce reproducible research reports for a fictional team. " * 5,
                capture_method=CaptureMethod.extension,
                captured_at=dt.datetime.now(dt.UTC),
                raw_metadata={},
            )
        )
        draft = {
            "summary": {"text": fact.statement, "supporting_fact_ids": [f"ach_{fact.id}"]},
            "experience": [],
            "projects": [],
            "skills": [],
        }
        sections = snapshot_sections(CVDraft.model_validate(draft), profile)
        version = CVVersion(job_id=job.id, version_number=1, sections=sections)
        session.add(version)
        session.commit()
        fixture = Workflow(job.id, version.id, sections, draft)
        fact_id, experience_id = fact.id, experience.id
    try:
        yield fixture
    finally:
        with SessionLocal() as session:
            session.execute(delete(Job).where(Job.id == fixture.job_id))
            session.execute(delete(CareerAchievement).where(CareerAchievement.id == fact_id))
            session.execute(delete(CareerExperience).where(CareerExperience.id == experience_id))
            session.commit()


def synchronize_writers(monkeypatch, *modules):
    """Start both real row-lock attempts together, before either can commit."""
    barrier = threading.Barrier(2)

    def synchronized(session, job_id, *, for_update=False):
        if for_update:
            barrier.wait(timeout=10)
        return get_job_or_404(session, job_id, for_update=for_update)

    for module in modules:
        monkeypatch.setattr(module, "get_job_or_404", synchronized)


def in_session(operation):
    with SessionLocal() as session:
        return operation(session)


def test_concurrent_edits_allocate_distinct_versions(workflow, monkeypatch):
    synchronize_writers(monkeypatch, cv)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                in_session,
                lambda session: (
                    cv.edit_version(
                        session, workflow.cv_id, copy.deepcopy(workflow.sections)
                    ).version_number
                ),
            )
            for _ in range(2)
        ]
        assert sorted(future.result(timeout=15) for future in futures) == [2, 3]


@pytest.mark.parametrize("other_writer", ["edit", "generate"])
def test_generation_shares_allocation_lock_with_other_cv_writers(
    workflow, monkeypatch, other_writer
):
    synchronize_writers(monkeypatch, generator, cv)

    def generate(session):
        provider = FakeLLMProvider([workflow.draft])
        version, _, _, _ = asyncio.run(
            generator.generate_cv(
                session, provider, job_id=workflow.job_id, request=GenerateCVRequest()
            )
        )
        return version.version_number

    other = (
        generate
        if other_writer == "generate"
        else lambda session: (
            cv.edit_version(
                session, workflow.cv_id, copy.deepcopy(workflow.sections)
            ).version_number
        )
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(in_session, writer) for writer in (generate, other)]
        assert sorted(future.result(timeout=15) for future in futures) == [2, 3]


def test_generation_does_not_lock_the_job_during_provider_await(workflow):
    class LockCheckingProvider(FakeLLMProvider):
        async def structured(self, **kwargs):
            with SessionLocal() as other:
                assert (
                    other.scalar(
                        select(Job).where(Job.id == workflow.job_id).with_for_update(nowait=True)
                    )
                    is not None
                )
            return await super().structured(**kwargs)

    with SessionLocal() as session:
        asyncio.run(
            generator.generate_cv(
                session,
                LockCheckingProvider([workflow.draft]),
                job_id=workflow.job_id,
                request=GenerateCVRequest(),
            )
        )


def test_generation_event_failure_rolls_back_version_and_success_run(workflow):
    def fail_generated_event(mapper, connection, target):
        if target.job_id == workflow.job_id and target.event_type == JobEventType.CV_GENERATED:
            raise RuntimeError("Synthetic event persistence failure")

    event.listen(JobEvent, "before_insert", fail_generated_event)
    try:
        with SessionLocal() as session:
            with pytest.raises(RuntimeError, match="Synthetic event"):
                asyncio.run(
                    generator.generate_cv(
                        session,
                        FakeLLMProvider([workflow.draft]),
                        job_id=workflow.job_id,
                        request=GenerateCVRequest(),
                    )
                )
            assert session.scalar(select(1)) == 1  # rollback leaves the session usable
    finally:
        event.remove(JobEvent, "before_insert", fail_generated_event)
    with SessionLocal() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(CVVersion)
                .where(CVVersion.job_id == workflow.job_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(CVGenerationRun)
                .where(CVGenerationRun.job_id == workflow.job_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(JobEvent)
                .where(
                    JobEvent.job_id == workflow.job_id,
                    JobEvent.event_type == JobEventType.CV_GENERATED,
                )
            )
            == 0
        )
        version, _, _, _ = asyncio.run(
            generator.generate_cv(
                session,
                FakeLLMProvider([workflow.draft]),
                job_id=workflow.job_id,
                request=GenerateCVRequest(),
            )
        )
        assert version.version_number == 2


def test_approval_refreshes_a_cached_status_after_another_session_applies(workflow):
    with SessionLocal() as approving, SessionLocal() as applying:
        cached = approving.get(Job, workflow.job_id)
        assert cached.current_status == JobStatus.SAVED
        applications.create_application(
            applying, job_id=workflow.job_id, submitted_cv_version_id=None
        )
        cv.approve_version(approving, workflow.cv_id)
        assert approving.get(Job, workflow.job_id).current_status == JobStatus.APPLIED


def test_concurrent_approval_and_application_preserve_applied_status(workflow, monkeypatch):
    synchronize_writers(monkeypatch, cv, applications)
    with ThreadPoolExecutor(max_workers=2) as pool:
        approve = pool.submit(
            in_session, lambda session: cv.approve_version(session, workflow.cv_id)
        )
        apply = pool.submit(
            in_session,
            lambda session: applications.create_application(
                session, job_id=workflow.job_id, submitted_cv_version_id=workflow.cv_id
            ),
        )
        approve.result(timeout=15)
        apply.result(timeout=15)
    with SessionLocal() as session:
        assert session.get(Job, workflow.job_id).current_status == JobStatus.APPLIED
        assert (
            session.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.job_id == workflow.job_id)
            )
            == 1
        )


def test_concurrent_apply_records_one_application_and_a_typed_conflict(workflow, monkeypatch):
    synchronize_writers(monkeypatch, applications)

    def apply(session):
        try:
            applications.create_application(
                session, job_id=workflow.job_id, submitted_cv_version_id=None
            )
        except IllegalTransitionError as error:
            return error.status_code
        return 201

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(in_session, apply) for _ in range(2)]
        assert sorted(future.result(timeout=15) for future in futures) == [201, 409]
    with SessionLocal() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.job_id == workflow.job_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ApplicationEvent)
                .join(Application)
                .where(
                    Application.job_id == workflow.job_id,
                    ApplicationEvent.event_type == "APPLICATION_SUBMITTED",
                )
            )
            == 1
        )


def test_concurrent_incompatible_application_events_do_not_overwrite_history(workflow, monkeypatch):
    with SessionLocal() as session:
        application_id = applications.create_application(
            session, job_id=workflow.job_id, submitted_cv_version_id=None
        ).id
    synchronize_writers(monkeypatch, applications)

    def record(kind):
        with SessionLocal() as session:
            try:
                applications.add_event(
                    session, application_id, event_type=kind, occurred_at=None, metadata={}
                )
            except IllegalTransitionError as error:
                return error.status_code
            return 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(record, kind) for kind in ("REJECTED", "OFFER_RECEIVED")]
        assert sorted(future.result(timeout=15) for future in futures) == [200, 409]
    with SessionLocal() as session:
        recorded = list(
            session.scalars(
                select(ApplicationEvent).where(
                    ApplicationEvent.application_id == application_id,
                    ApplicationEvent.event_type != "APPLICATION_SUBMITTED",
                )
            )
        )
        assert len(recorded) == 1
        expected = JobStatus.REJECTED if recorded[0].event_type == "REJECTED" else JobStatus.OFFER
        assert session.get(Job, workflow.job_id).current_status == expected


def test_concurrent_manual_marker_and_application_agree_on_recorded_cv(workflow, monkeypatch):
    with SessionLocal() as session:
        other_cv = cv.edit_version(session, workflow.cv_id, copy.deepcopy(workflow.sections)).id
    synchronize_writers(monkeypatch, cv, applications)

    def mark(session):
        try:
            cv.mark_submitted(session, other_cv)
        except ConflictError as error:
            return error.status_code
        return 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        marker = pool.submit(in_session, mark)
        application = pool.submit(
            in_session,
            lambda session: applications.create_application(
                session, job_id=workflow.job_id, submitted_cv_version_id=workflow.cv_id
            ),
        )
        assert marker.result(timeout=15) in (200, 409)
        application_id = application.result(timeout=15).id
    with SessionLocal() as session:
        assert session.get(Application, application_id).submitted_cv_version_id == workflow.cv_id
        submitted = list(
            session.scalars(
                select(CVVersion.id).where(
                    CVVersion.job_id == workflow.job_id, CVVersion.is_submitted.is_(True)
                )
            )
        )
        assert submitted == [workflow.cv_id]


def test_manual_marker_refreshes_a_stale_true_identity_map(workflow):
    with SessionLocal() as session:
        other_cv = cv.edit_version(session, workflow.cv_id, copy.deepcopy(workflow.sections)).id
        cv.mark_submitted(session, workflow.cv_id)
    with SessionLocal() as stale, SessionLocal() as other:
        cached = stale.get(CVVersion, workflow.cv_id)
        assert cached.is_submitted
        cv.mark_submitted(other, other_cv)
        cv.mark_submitted(stale, workflow.cv_id)
    with SessionLocal() as session:
        submitted = list(
            session.scalars(
                select(CVVersion.id).where(
                    CVVersion.job_id == workflow.job_id, CVVersion.is_submitted.is_(True)
                )
            )
        )
        assert submitted == [workflow.cv_id]
