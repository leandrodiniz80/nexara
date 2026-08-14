from typing import Any, ClassVar

import pytest

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.exceptions.task_exceptions import TaskNotRegisteredError
from app.application.tasks.registry.task_registry import TaskRegistry


class _StubTask(ApplicationTask):
    task_type: ClassVar[TaskType] = TaskType.QUALIFICATION
    name: ClassVar[str] = "stub_task"

    def validate(self, context: TaskContext) -> None:
        pass

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        return {}

    async def rollback(self, context: TaskContext) -> None:
        pass


def test_register_and_get_round_trips():
    registry = TaskRegistry()
    task = _StubTask()

    registry.register(task)

    assert registry.get(TaskType.QUALIFICATION) is task


def test_get_unregistered_task_type_raises():
    registry = TaskRegistry()

    with pytest.raises(TaskNotRegisteredError):
        registry.get(TaskType.COPY)


def test_list_registered_reflects_what_was_registered():
    registry = TaskRegistry()
    registry.register(_StubTask())

    assert registry.list_registered() == [TaskType.QUALIFICATION]
