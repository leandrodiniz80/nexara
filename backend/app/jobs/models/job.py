import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.jobs.models.enums import JobPriority, JobStatus


class Job(BaseModel):
    """Every long-running execution on the platform is represented by one of these —
    searching companies, generating emails, running a workflow, importing a CSV,
    calling AI, generating a proposal. Job doesn't know which of those it actually is
    (that's `job_type`, a free string, and `pipeline_name`); it only knows the
    lifecycle every one of them goes through.

    Mutable on purpose (unlike an events/DomainEvent): JobEngine updates the same
    instance in place as the job progresses through its lifecycle.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    job_type: str
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    progress: int = Field(0, ge=0, le=100)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    execution_time: float | None = None
    requested_by: uuid.UUID | None = None
    mission_id: uuid.UUID | None = None
    pipeline_name: str | None = None
    current_step: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
