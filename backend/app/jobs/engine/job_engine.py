import uuid
from datetime import datetime, timezone
from typing import Any

from app.jobs.exceptions.transition_exceptions import InvalidJobTransitionError
from app.jobs.models.enums import JobPriority, JobStatus
from app.jobs.models.job import Job
from app.jobs.repositories.job_repository import JobRepository
from app.jobs.schemas.job_execution_log import JobExecutionLog

_ACTIVE_STATUSES = {JobStatus.PENDING, JobStatus.WAITING, JobStatus.RUNNING, JobStatus.PAUSED}


class JobEngine:
    """Owns the Job lifecycle (create -> start -> pause/resume -> finish/fail/cancel)
    and its execution log — the same lifecycle-engine shape as MissionEngine/
    ProspectEngine, applied to "one execution" instead of "one mission"/"one
    opportunity".

    Deliberately synchronous: unlike MissionEngine (backed by a real async SQLAlchemy
    session), JobRepository is pure in-memory with no I/O to await — making every
    method here `async def` would just be a false promise of asynchrony with nothing
    underneath it, which is not more "correct", just noisier.
    """

    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository
        self._execution_logs: list[JobExecutionLog] = []

    def create(
        self,
        *,
        job_type: str,
        priority: JobPriority = JobPriority.NORMAL,
        requested_by: uuid.UUID | None = None,
        mission_id: uuid.UUID | None = None,
        pipeline_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Job:
        job = self.repository.create(
            job_type=job_type,
            status=JobStatus.PENDING,
            priority=priority,
            progress=0,
            requested_by=requested_by,
            mission_id=mission_id,
            pipeline_name=pipeline_name,
            metadata=metadata or {},
        )
        self._log(job, message=f"Job '{job.job_type}' created.")
        return job

    @staticmethod
    def _ensure_status(job: Job, allowed: set[JobStatus], action: str) -> None:
        if job.status not in allowed:
            raise InvalidJobTransitionError(job.id, job.status, action)

    def start(self, job: Job) -> Job:
        self._ensure_status(job, {JobStatus.PENDING, JobStatus.WAITING}, "start")
        job = self.repository.update(
            job, status=JobStatus.RUNNING, started_at=datetime.now(timezone.utc)
        )
        self._log(job, message="Job started.")
        return job

    def pause(self, job: Job) -> Job:
        self._ensure_status(job, {JobStatus.RUNNING}, "pause")
        job = self.repository.update(job, status=JobStatus.PAUSED)
        self._log(job, message="Job paused.")
        return job

    def resume(self, job: Job) -> Job:
        self._ensure_status(job, {JobStatus.PAUSED}, "resume")
        job = self.repository.update(job, status=JobStatus.RUNNING)
        self._log(job, message="Job resumed.")
        return job

    def cancel(self, job: Job, *, reason: str | None = None) -> Job:
        self._ensure_status(job, _ACTIVE_STATUSES, "cancel")
        job = self.repository.update(
            job,
            status=JobStatus.CANCELLED,
            finished_at=datetime.now(timezone.utc),
            error_message=reason,
        )
        job = self._stamp_execution_time(job)
        self._log(job, message=reason or "Job cancelled.")
        return job

    def finish(self, job: Job, *, output: dict[str, Any] | None = None) -> Job:
        self._ensure_status(job, {JobStatus.RUNNING}, "finish")
        attrs: dict[str, Any] = {
            "status": JobStatus.FINISHED,
            "finished_at": datetime.now(timezone.utc),
            "progress": 100,
        }
        if output is not None:
            attrs["metadata"] = {**job.metadata, "output": output}
        job = self.repository.update(job, **attrs)
        job = self._stamp_execution_time(job)
        self._log(job, message="Job finished.")
        return job

    def fail(self, job: Job, *, error_message: str) -> Job:
        self._ensure_status(job, {JobStatus.RUNNING}, "fail")
        job = self.repository.update(
            job,
            status=JobStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_message=error_message,
        )
        job = self._stamp_execution_time(job)
        self._log(job, message=error_message)
        return job

    def update_progress(self, job: Job, *, progress: int, current_step: str | None = None) -> Job:
        self._ensure_status(job, {JobStatus.RUNNING}, "update_progress")
        attrs: dict[str, Any] = {"progress": max(0, min(100, progress))}
        if current_step is not None:
            attrs["current_step"] = current_step
        job = self.repository.update(job, **attrs)
        self._log(job, step=job.current_step, message=f"Progress: {job.progress}%")
        return job

    def _stamp_execution_time(self, job: Job) -> Job:
        if job.started_at is not None and job.finished_at is not None:
            delta = (job.finished_at - job.started_at).total_seconds()
            return self.repository.update(job, execution_time=delta)
        return job

    def _log(
        self, job: Job, *, step: str | None = None, message: str | None = None
    ) -> JobExecutionLog:
        log = JobExecutionLog(
            job_id=job.id,
            execution_time=job.execution_time or 0.0,
            status=job.status,
            step=step,
            message=message,
        )
        self._execution_logs.append(log)
        return log

    def list_execution_logs(self) -> list[JobExecutionLog]:
        return list(self._execution_logs)
