from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class PerformanceMetric(BaseModel):
    """One recorded performance sample for one operation. Frozen, same reasoning
    as AuditEntry/ExecutionStep: a metric is a fact about the past, never updated.

    `memory_usage`/`cpu_usage` are optional — not every caller can (or bothers to)
    report resource usage alongside timing; `execution_time`/`success` are the only
    two fields every recorded metric is expected to always have.
    """

    model_config = ConfigDict(frozen=True)

    component: str
    operation: str
    execution_time: float
    memory_usage: float | None = None
    cpu_usage: float | None = None
    success: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
