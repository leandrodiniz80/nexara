import enum
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.crm.services.sales_cadence_step import SalesCadenceStep


class SalesCadenceExecutionStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    FINISHED = "finished"


class SalesCadenceExecution(BaseModel):
    """Tracks which step of a SalesCadence one opportunity is currently at —
    mutable, like every other lifecycle entity in this platform (Job,
    WorkflowExecution, CRMOpportunity): SalesCadenceExecutionService updates
    the same instance in place as start()/advance()/rollback()/pause()/
    resume()/finish() are called. Nothing here is persisted anywhere; this
    is purely in-memory state for as long as its caller holds a reference to
    it.

    `current_step`/`completed_steps`/`remaining_steps` always reference the
    exact same SalesCadenceStep objects the originating SalesCadence
    provided — never a reconstructed or mutated copy of one.
    """

    current_step: SalesCadenceStep | None = None
    completed_steps: list[SalesCadenceStep] = Field(default_factory=list)
    remaining_steps: list[SalesCadenceStep] = Field(default_factory=list)
    status: SalesCadenceExecutionStatus = SalesCadenceExecutionStatus.NOT_STARTED
    started_at: datetime | None = None
    last_activity: datetime | None = None
    next_due_date: date | None = None
    finished_at: datetime | None = None
    progress: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
