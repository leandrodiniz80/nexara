import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.automation.models.enums import AutomationStatus


class AutomationExecution(BaseModel):
    """One firing of an Automation — mutable, like WorkflowExecution/Job:
    AutomationEngine updates the same instance in place as the underlying
    WorkflowEngine.execute() call resolves.

    `workflow_execution_id` is a bare reference to the WorkflowExecution that ran
    (WorkflowResult.execution.execution_id) — never the full object embedded here,
    the same "reference by id, not by value" convention every other module in this
    platform already uses.
    """

    execution_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    automation_id: uuid.UUID
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: AutomationStatus = AutomationStatus.RUNNING
    workflow_execution_id: uuid.UUID | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
