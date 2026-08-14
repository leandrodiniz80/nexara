from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.exceptions.task_exceptions import TaskNotRegisteredError


class TaskRegistry:
    """In-memory lookup of ApplicationTask instances by TaskType — register once
    (typically by TaskFactory, at composition time), look up by type thereafter.
    Mirrors AIOrchestrator's `_agents: dict[AgentType, AgentBase]` registry, one
    layer up."""

    def __init__(self) -> None:
        self._tasks: dict[TaskType, ApplicationTask] = {}

    def register(self, task: ApplicationTask) -> None:
        self._tasks[task.task_type] = task

    def get(self, task_type: TaskType) -> ApplicationTask:
        try:
            return self._tasks[task_type]
        except KeyError as exc:
            raise TaskNotRegisteredError(task_type) from exc

    def list_registered(self) -> list[TaskType]:
        return list(self._tasks.keys())
