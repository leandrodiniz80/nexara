from typing import Any

from app.application.tasks.base.application_task import TaskType
from app.workflows.models.workflow import Workflow
from app.workflows.models.workflow_step import WorkflowStep


class WorkflowBuilder:
    """Deterministic construction of Workflow/WorkflowStep — pure functions of
    their inputs, no I/O, no AI, no database. Every default workflow
    (default_workflows.py) and every future custom workflow is built through this,
    never by constructing Workflow/WorkflowStep directly elsewhere.
    """

    @staticmethod
    def build_step(
        *,
        order: int,
        task_type: TaskType,
        name: str,
        required: bool = True,
        continue_on_error: bool = False,
        timeout: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowStep:
        return WorkflowStep(
            order=order,
            task_type=task_type,
            name=name,
            required=required,
            continue_on_error=continue_on_error,
            timeout=timeout,
            metadata=metadata or {},
        )

    @staticmethod
    def build_workflow(
        *,
        name: str,
        steps: list[WorkflowStep],
        description: str | None = None,
        version: int = 1,
        is_active: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        return Workflow(
            name=name,
            description=description,
            steps=steps,
            version=version,
            is_active=is_active,
            metadata=metadata or {},
        )
