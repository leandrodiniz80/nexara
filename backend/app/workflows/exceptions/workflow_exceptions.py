import uuid
from typing import TYPE_CHECKING

from app.workflows.exceptions.base import WorkflowError

if TYPE_CHECKING:
    from app.application.tasks.base.application_task import TaskType
    from app.workflows.models.enums import WorkflowStatus


class WorkflowNotFoundError(WorkflowError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No active workflow registered for '{name}'.")


class WorkflowVersionNotFoundError(WorkflowError):
    def __init__(self, name: str, version: int) -> None:
        self.name = name
        self.version = version
        super().__init__(f"Workflow '{name}' has no version {version}.")


class TaskNotAvailableError(WorkflowError):
    """Raised when a WorkflowStep references a TaskType the engine wasn't given a
    task for — a wiring problem in whatever built the engine, not a business rule."""

    def __init__(self, task_type: "TaskType") -> None:
        self.task_type = task_type
        super().__init__(f"No ApplicationTask available for TaskType.{task_type.name}.")


class InvalidWorkflowTransitionError(WorkflowError):
    """`execution_id`/`current_status` are typed against WorkflowStatus for
    callers/type-checkers only — this module intentionally has no runtime
    dependency on app.workflows.models (exceptions are a leaf package)."""

    def __init__(
        self, execution_id: uuid.UUID, current_status: "WorkflowStatus", action: str
    ) -> None:
        self.execution_id = execution_id
        self.current_status = current_status
        self.action = action
        super().__init__(
            f"Cannot {action} execution {execution_id}: it is '{current_status.value}'."
        )
