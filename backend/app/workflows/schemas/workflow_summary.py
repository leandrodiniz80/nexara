import uuid

from pydantic import BaseModel

from app.application.tasks.base.application_task import TaskType
from app.workflows.models.workflow import Workflow


class WorkflowSummary(BaseModel):
    """A condensed, read-only view of a Workflow definition — what a listing of
    registered workflows would show without needing every step's full detail."""

    workflow_id: uuid.UUID
    name: str
    version: int
    is_active: bool
    step_count: int
    task_types: list[TaskType]

    @classmethod
    def from_workflow(cls, workflow: Workflow) -> "WorkflowSummary":
        ordered_steps = sorted(workflow.steps, key=lambda step: step.order)
        return cls(
            workflow_id=workflow.id,
            name=workflow.name,
            version=workflow.version,
            is_active=workflow.is_active,
            step_count=len(workflow.steps),
            task_types=[step.task_type for step in ordered_steps],
        )
