import uuid

from app.jobs.exceptions.base import JobError
from app.jobs.models.enums import JobStatus


class InvalidJobTransitionError(JobError):
    """Raised when a JobEngine lifecycle method is called from a JobStatus it doesn't
    allow (e.g. pause() on a job that isn't RUNNING)."""

    def __init__(self, job_id: uuid.UUID, current_status: JobStatus, action: str) -> None:
        self.job_id = job_id
        self.current_status = current_status
        self.action = action
        super().__init__(f"Cannot {action} job {job_id}: it is '{current_status.value}'.")
