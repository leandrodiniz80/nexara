import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.jobs.models.enums import JobStatus


class JobExecutionLog(BaseModel):
    """One audit-trail row for a Job lifecycle transition — recorded by JobEngine for
    every create/start/pause/resume/cancel/finish/fail/update_progress call."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    job_id: uuid.UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time: float
    status: JobStatus
    step: str | None = None
    message: str | None = None
