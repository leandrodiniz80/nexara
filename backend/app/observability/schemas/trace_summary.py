import uuid
from datetime import datetime

from pydantic import BaseModel

from app.observability.models.execution_step import ExecutionStatus
from app.observability.models.execution_trace import ExecutionTrace


class TraceSummary(BaseModel):
    """A condensed, read-only view of an ExecutionTrace — everything a dashboard
    listing traces would show without needing every step's full detail."""

    trace_id: uuid.UUID
    execution_type: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None
    duration: float | None
    step_count: int
    error_count: int
    warning_count: int

    @classmethod
    def from_trace(cls, trace: ExecutionTrace) -> "TraceSummary":
        return cls(
            trace_id=trace.trace_id,
            execution_type=trace.execution_type,
            status=trace.status,
            started_at=trace.started_at,
            finished_at=trace.finished_at,
            duration=trace.duration,
            step_count=len(trace.steps),
            error_count=sum(len(step.errors) for step in trace.steps),
            warning_count=sum(len(step.warnings) for step in trace.steps),
        )
