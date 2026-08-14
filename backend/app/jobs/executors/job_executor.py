from abc import ABC, abstractmethod

from app.jobs.models.job import Job
from app.jobs.schemas.job_result import JobResult


class JobExecutor(ABC):
    """Runs one Job to completion. From this point on, nothing in the platform should
    run a long execution (a pipeline, a workflow, an AI call) directly — it wraps that
    execution in a JobExecutor instead, so JobEngine has a lifecycle/progress/log
    record of it regardless of what actually did the work.
    """

    @abstractmethod
    async def execute(self, job: Job) -> JobResult:
        """Run `job` and report the outcome. Implementations are responsible for
        calling JobEngine.start()/finish()/fail() themselves — the executor is what
        connects "some piece of work" to "the Job lifecycle", not JobEngine itself."""
