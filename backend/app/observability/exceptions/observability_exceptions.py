import uuid

from app.observability.exceptions.base import ObservabilityError
from app.observability.models.execution_step import ExecutionStatus


class TraceNotFoundError(ObservabilityError):
    def __init__(self, trace_id: uuid.UUID) -> None:
        self.trace_id = trace_id
        super().__init__(f"ExecutionTrace {trace_id} not found.")


class InvalidTraceTransitionError(ObservabilityError):
    """Raised when finish_trace()/register_step() is called on a trace that isn't
    RUNNING — the same "guard the state machine" convention every other engine in
    this platform already follows (MissionEngine, JobEngine, ApprovalService), not
    a business decision: a trace that's already finished has nothing left to record."""

    def __init__(self, trace_id: uuid.UUID, current_status: ExecutionStatus, action: str) -> None:
        self.trace_id = trace_id
        self.current_status = current_status
        self.action = action
        super().__init__(f"Cannot {action} trace {trace_id}: it is '{current_status.value}'.")
