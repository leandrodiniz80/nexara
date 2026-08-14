import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(str, enum.Enum):
    """Closed vocabulary shared by ExecutionStep and ExecutionTrace — always
    exactly one of these, unlike `execution_type`/`component`/`action` elsewhere in
    this module (free strings, open vocabularies). Defined here rather than in
    execution_trace.py so ExecutionTrace can import ExecutionStep (for its `steps`
    field) without either module needing the other back — no forward reference, no
    circular import."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ExecutionStep(BaseModel):
    """One completed step within an ExecutionTrace — frozen, like every other log
    entry in this module (AuditEntry, PerformanceMetric): a step is recorded once
    its start and end are both already known, never mutated afterward. The trace it
    belongs to is what's mutable (its `steps` list grows), not the step itself.
    """

    model_config = ConfigDict(frozen=True)

    step_name: str
    component: str
    started_at: datetime
    finished_at: datetime
    duration: float
    status: ExecutionStatus
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
