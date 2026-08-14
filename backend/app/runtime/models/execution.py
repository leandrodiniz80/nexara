import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.runtime.models.enums import ExecutionStatus, ExecutionType


class Execution(BaseModel):
    """One tracked run of *anything* the Runtime executes — a Workflow today, a
    Job/Pipeline/Agent tomorrow. Mutable, like every other lifecycle entity in this
    platform (Job, WorkflowExecution, AutomationExecution): the Executor that owns
    one updates it in place from CREATED -> RUNNING -> SUCCESS/FAILED/CANCELLED.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    execution_type: ExecutionType
    status: ExecutionStatus = ExecutionStatus.CREATED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
