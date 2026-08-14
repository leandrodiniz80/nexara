from types import SimpleNamespace

from app.jobs.executors.pipeline_job_executor import PipelineJobExecutor
from app.jobs.models.enums import JobStatus
from app.jobs.models.job import Job
from app.jobs.repositories.job_repository import JobRepository
from app.jobs.services.job_engine_factory import build_default_job_engine


class _FakeReport:
    """Deliberately unrelated to app.research.pipeline.PipelineReport — proves
    PipelineJobExecutor works by shape, not by importing any specific pipeline."""

    def __init__(self, errors=None, warnings=None):
        self.errors = errors or []
        self.warnings = warnings or []

    def model_dump(self, mode="json"):
        return {"errors": self.errors, "warnings": self.warnings}


class _FakePipeline:
    def __init__(self, report: _FakeReport) -> None:
        self.report = report
        self.received_context = None

    async def execute(self, context):
        self.received_context = context
        return self.report


async def test_successful_pipeline_run_finishes_the_job():
    engine = build_default_job_engine(repository=JobRepository())
    job = engine.create(job_type="lead_discovery")
    pipeline = _FakePipeline(_FakeReport())
    executor = PipelineJobExecutor(
        pipeline, context_factory=lambda j: {"job_id": str(j.id)}, job_engine=engine
    )

    result = await executor.execute(job)

    assert result.success is True
    assert job.status == JobStatus.FINISHED
    assert job.progress == 100
    assert pipeline.received_context == {"job_id": str(job.id)}


async def test_pipeline_reporting_errors_fails_the_job():
    engine = build_default_job_engine(repository=JobRepository())
    job = engine.create(job_type="lead_discovery")
    pipeline = _FakePipeline(_FakeReport(errors=["provider unavailable"]))
    executor = PipelineJobExecutor(pipeline, context_factory=lambda j: None, job_engine=engine)

    result = await executor.execute(job)

    assert result.success is False
    assert result.errors == ["provider unavailable"]
    assert job.status == JobStatus.FAILED
    assert job.error_message == "provider unavailable"


async def test_pipeline_raising_an_exception_fails_the_job_without_propagating():
    engine = build_default_job_engine(repository=JobRepository())
    job = engine.create(job_type="lead_discovery")

    class _BrokenPipeline:
        async def execute(self, context):
            raise RuntimeError("boom")

    executor = PipelineJobExecutor(
        _BrokenPipeline(), context_factory=lambda j: None, job_engine=engine
    )

    result = await executor.execute(job)

    assert result.success is False
    assert "boom" in result.errors[0]
    assert job.status == JobStatus.FAILED


async def test_executor_works_with_a_report_that_has_no_errors_warnings_attributes():
    """Duck-typing fallback: a report shape with neither `errors` nor `warnings` is
    still treated as a success — PipelineJobExecutor never assumes PipelineReport
    specifically."""
    engine = build_default_job_engine(repository=JobRepository())
    job = engine.create(job_type="anything")
    bare_report = SimpleNamespace()  # no .errors, no .warnings, no .model_dump
    pipeline = _FakePipeline(bare_report)
    executor = PipelineJobExecutor(pipeline, context_factory=lambda j: None, job_engine=engine)

    result = await executor.execute(job)

    assert result.success is True
    assert result.errors == []
    assert result.warnings == []
    assert job.status == JobStatus.FINISHED
