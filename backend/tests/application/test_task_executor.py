from typing import Any, ClassVar

import pytest

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.executors.task_executor import TaskExecutor


class _EchoTask(ApplicationTask):
    task_type: ClassVar[TaskType] = TaskType.RESEARCH
    name: ClassVar[str] = "echo_task"

    def validate(self, context: TaskContext) -> None:
        if "instruction" not in context.variables:
            raise ValueError("instruction is required")

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        return {"echo": context.variables["instruction"]}

    async def rollback(self, context: TaskContext) -> None:
        pass


class _BrokenTask(_EchoTask):
    name: ClassVar[str] = "broken_task"

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        raise RuntimeError("boom")


class _RollbackTrackingTask(_EchoTask):
    name: ClassVar[str] = "rollback_tracking_task"

    def __init__(self) -> None:
        self.rolled_back = False

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        raise RuntimeError("boom")

    async def rollback(self, context: TaskContext) -> None:
        self.rolled_back = True


class _RollbackAlsoFailsTask(_BrokenTask):
    name: ClassVar[str] = "rollback_also_fails_task"

    async def rollback(self, context: TaskContext) -> None:
        raise RuntimeError("rollback boom")


async def test_executor_success_path():
    result = await TaskExecutor().run(_EchoTask(), TaskContext(variables={"instruction": "x"}))

    assert result.success is True
    assert result.output == {"echo": "x"}
    assert result.duration >= 0
    assert any("validated" in log for log in result.logs)
    assert any("executed" in log for log in result.logs)


async def test_executor_wraps_validation_failure():
    result = await TaskExecutor().run(_EchoTask(), TaskContext(variables={}))

    assert result.success is False
    assert result.output is None
    assert any("failed" in log for log in result.logs)


async def test_executor_wraps_execution_failure_and_calls_rollback():
    task = _RollbackTrackingTask()
    result = await TaskExecutor().run(task, TaskContext(variables={"instruction": "x"}))

    assert result.success is False
    assert result.errors == ["boom"]
    assert task.rolled_back is True
    assert any("rolled back" in log for log in result.logs)


def test_application_task_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ApplicationTask()


async def test_executor_survives_a_failing_rollback_too():
    result = await TaskExecutor().run(
        _RollbackAlsoFailsTask(), TaskContext(variables={"instruction": "x"})
    )

    assert result.success is False
    assert result.errors == ["boom"]
    assert any("rollback also failed" in log for log in result.logs)
