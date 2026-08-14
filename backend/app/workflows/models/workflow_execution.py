import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.workflows.models.enums import WorkflowStatus


class WorkflowExecution(BaseModel):
    """One run of a Workflow — mutable, like Job/Mission/ExecutionTrace:
    WorkflowEngine updates the same instance in place as execute_workflow()/
    resume()/retry()/cancel() progress through it.

    `current_step`/`completed_steps`/`failed_steps` all hold WorkflowStep.order
    values (not the steps themselves) — an execution references its workflow's
    steps by position, it doesn't duplicate their definitions.
    """

    workflow_id: uuid.UUID
    execution_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int | None = None
    completed_steps: list[int] = Field(default_factory=list)
    failed_steps: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
