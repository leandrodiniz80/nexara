import pytest

from app.jobs.engine.job_engine import JobEngine
from app.jobs.exceptions.transition_exceptions import InvalidJobTransitionError
from app.jobs.models.enums import JobPriority, JobStatus
from app.jobs.repositories.job_repository import JobRepository


def _engine() -> JobEngine:
    return JobEngine(JobRepository())


def test_create_starts_a_job_in_pending_with_zero_progress():
    engine = _engine()
    job = engine.create(job_type="lead_discovery", priority=JobPriority.HIGH)

    assert job.status == JobStatus.PENDING
    assert job.progress == 0
    assert job.priority == JobPriority.HIGH
    logs = engine.list_execution_logs()
    assert len(logs) == 1
    assert "created" in logs[0].message


def test_full_lifecycle_happy_path():
    engine = _engine()
    job = engine.create(job_type="lead_discovery")

    job = engine.start(job)
    assert job.status == JobStatus.RUNNING
    assert job.started_at is not None

    job = engine.pause(job)
    assert job.status == JobStatus.PAUSED

    job = engine.resume(job)
    assert job.status == JobStatus.RUNNING

    job = engine.update_progress(job, progress=50, current_step="searching")
    assert job.progress == 50
    assert job.current_step == "searching"

    job = engine.finish(job, output={"total_found": 35})
    assert job.status == JobStatus.FINISHED
    assert job.progress == 100
    assert job.finished_at is not None
    assert job.execution_time is not None
    assert job.execution_time >= 0
    assert job.metadata["output"] == {"total_found": 35}


def test_fail_records_the_error_message_and_stamps_execution_time():
    engine = _engine()
    job = engine.start(engine.create(job_type="lead_discovery"))

    job = engine.fail(job, error_message="provider timed out")

    assert job.status == JobStatus.FAILED
    assert job.error_message == "provider timed out"
    assert job.execution_time is not None


def test_cancel_is_allowed_from_pending():
    engine = _engine()
    job = engine.create(job_type="lead_discovery")

    job = engine.cancel(job, reason="duplicate request")

    assert job.status == JobStatus.CANCELLED
    assert job.error_message == "duplicate request"


def test_cannot_pause_a_job_that_is_not_running():
    engine = _engine()
    job = engine.create(job_type="lead_discovery")

    with pytest.raises(InvalidJobTransitionError):
        engine.pause(job)


def test_cannot_finish_a_job_that_never_started():
    engine = _engine()
    job = engine.create(job_type="lead_discovery")

    with pytest.raises(InvalidJobTransitionError):
        engine.finish(job)


def test_cannot_cancel_a_finished_job():
    engine = _engine()
    job = engine.finish(engine.start(engine.create(job_type="lead_discovery")))

    with pytest.raises(InvalidJobTransitionError):
        engine.cancel(job)


def test_progress_is_clamped_between_0_and_100():
    engine = _engine()
    job = engine.start(engine.create(job_type="lead_discovery"))

    job = engine.update_progress(job, progress=250)
    assert job.progress == 100

    job = engine.update_progress(job, progress=-10)
    assert job.progress == 0


def test_execution_logs_accumulate_across_the_lifecycle():
    engine = _engine()
    job = engine.create(job_type="lead_discovery")
    job = engine.start(job)
    engine.finish(job)

    logs = engine.list_execution_logs()
    assert len(logs) == 3  # created, started, finished
    statuses = [log.status for log in logs]
    assert statuses == [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.FINISHED]
