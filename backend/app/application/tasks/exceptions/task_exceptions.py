from typing import TYPE_CHECKING

from app.application.tasks.exceptions.base import ApplicationTaskError

if TYPE_CHECKING:
    from app.application.tasks.base.application_task import TaskType


class TaskValidationError(ApplicationTaskError):
    """Raised by ApplicationTask.validate() when TaskContext is missing what that
    task needs to run."""


class TaskExecutionError(ApplicationTaskError):
    """Raised when a task's underlying module call fails in a way that isn't a
    validation problem."""


class TaskNotRegisteredError(ApplicationTaskError):
    """`task_type` is typed against TaskType for callers/type-checkers only — this
    module intentionally has no runtime dependency on `app.application.tasks.base`
    (exceptions are a leaf package; nothing should depend on the task base classes
    just to raise an error about one)."""

    def __init__(self, task_type: "TaskType") -> None:
        self.task_type = task_type
        super().__init__(f"No task registered for TaskType.{task_type.name}.")
