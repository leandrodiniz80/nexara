import time
from typing import Any, Callable, Protocol

from app.jobs.engine.job_engine import JobEngine
from app.jobs.executors.job_executor import JobExecutor
from app.jobs.models.job import Job
from app.jobs.schemas.job_result import JobResult


class _SupportsPipelineExecute(Protocol):
    async def execute(self, context: Any) -> Any: ...


def _as_list(value: Any) -> list[str]:
    return list(value) if value else []


def _as_dict(report: Any) -> dict[str, Any] | None:
    dump = getattr(report, "model_dump", None)
    return dump(mode="json") if callable(dump) else None


class PipelineJobExecutor(JobExecutor):
    """Generic adapter: runs *any* object exposing an async `execute(context) -> report`
    method as a Job — LeadDiscoveryPipeline today, whatever pipeline comes next
    tomorrow, all through this exact same class.

    The only assumption made about `pipeline` is that single method's shape (checked
    structurally via `_SupportsPipelineExecute`, not by importing the pipeline's own
    class). `report.errors`/`report.warnings` are read back with `getattr(..., None)`
    rather than assumed to exist, so this doesn't even require the report to look like
    PipelineReport specifically — a pipeline is never modified, or even imported by
    name, to be run this way.
    """

    def __init__(
        self,
        pipeline: _SupportsPipelineExecute,
        context_factory: Callable[[Job], Any],
        job_engine: JobEngine,
    ) -> None:
        self.pipeline = pipeline
        self.context_factory = context_factory
        self.job_engine = job_engine

    async def execute(self, job: Job) -> JobResult:
        start = time.perf_counter()
        self.job_engine.start(job)
        self.job_engine.update_progress(job, progress=10, current_step="running_pipeline")

        try:
            context = self.context_factory(job)
            report = await self.pipeline.execute(context)
        except Exception as exc:
            self.job_engine.fail(job, error_message=str(exc))
            return JobResult(success=False, duration=time.perf_counter() - start, errors=[str(exc)])

        errors = _as_list(getattr(report, "errors", None))
        warnings = _as_list(getattr(report, "warnings", None))
        output = _as_dict(report)

        self.job_engine.update_progress(job, progress=90, current_step="pipeline_completed")
        if errors:
            self.job_engine.fail(job, error_message="; ".join(errors))
        else:
            self.job_engine.finish(job, output=output)

        return JobResult(
            success=not errors,
            duration=time.perf_counter() - start,
            warnings=warnings,
            errors=errors,
            output=output,
        )
