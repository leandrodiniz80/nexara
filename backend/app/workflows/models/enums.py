import enum


class WorkflowStatus(str, enum.Enum):
    """Closed vocabulary for WorkflowExecution.status. PAUSED (not FAILED) is what
    a required step failing (continue_on_error=False) produces — "workflow
    interrompe", recoverable via resume()/retry(), not a terminal failure."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
