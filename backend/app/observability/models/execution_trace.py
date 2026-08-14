import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.observability.models.execution_step import ExecutionStatus, ExecutionStep


class ExecutionTrace(BaseModel):
    """One tracked execution — a Mission being created, a Task running, an AI call
    — from start to finish. Mutable on purpose (like Job/Mission): ObservabilityEngine
    updates the same instance in place as start_trace()/register_step()/finish_trace()
    are called, the same "live entity, not an append-only log row" shape as Job.

    `execution_type` is a free string (e.g. "mission_creation", "copy_generation")
    — this module doesn't own a closed list of every kind of execution the platform
    might ever want to trace, the same reasoning as Job.job_type.
    """

    trace_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    correlation_id: uuid.UUID | None = None
    request_id: str | None = None
    mission_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    execution_type: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    duration: float | None = None
    status: ExecutionStatus = ExecutionStatus.RUNNING
    steps: list[ExecutionStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
