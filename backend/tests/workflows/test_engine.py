import asyncio
import uuid
from typing import Any, ClassVar

import pytest

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.executors.task_executor import TaskExecutor
from app.workflows.builders.workflow_builder import WorkflowBuilder
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.exceptions.workflow_exceptions import (
    InvalidWorkflowTransitionError,
    TaskNotAvailableError,
)
from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow_execution import WorkflowExecution
from app.workflows.registry.workflow_registry import WorkflowRegistry
from app.workflows.repositories.workflow_repository import WorkflowRepository


class _SucceedingTask(ApplicationTask):
    name: ClassVar[str] = "succeeding_task"

    def __init__(self, task_type: TaskType, output: dict[str, Any] | None = None) -> None:
        self.task_type = task_type
        self._output = output if output is not None else {}

    def validate(self, context: TaskContext) -> None:
        pass

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        return self._output

    async def rollback(self, context: TaskContext) -> None:
        pass


class _FailingTask(ApplicationTask):
    name: ClassVar[str] = "failing_task"

    def __init__(self, task_type: TaskType, error: str = "boom") -> None:
        self.task_type = task_type
        self._error = error

    def validate(self, context: TaskContext) -> None:
        pass

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        raise RuntimeError(self._error)

    async def rollback(self, context: TaskContext) -> None:
        pass


class _SlowTask(ApplicationTask):
    name: ClassVar[str] = "slow_task"

    def __init__(self, task_type: TaskType, delay: float) -> None:
        self.task_type = task_type
        self._delay = delay

    def validate(self, context: TaskContext) -> None:
        pass

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        await asyncio.sleep(self._delay)
        return {}

    async def rollback(self, context: TaskContext) -> None:
        pass


def _build_engine(tasks: dict[TaskType, ApplicationTask]) -> WorkflowEngine:
    return WorkflowEngine(
        repository=WorkflowRepository(),
        registry=WorkflowRegistry(),
        tasks=tasks,
        task_executor=TaskExecutor(),
    )


def _two_step_workflow(*, continue_on_error: bool):
    steps = [
        WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research"),
        WorkflowBuilder.build_step(
            order=2,
            task_type=TaskType.QUALIFICATION,
            name="qualification",
            continue_on_error=continue_on_error,
        ),
        WorkflowBuilder.build_step(order=3, task_type=TaskType.COPY, name="copy_generation"),
    ]
    return WorkflowBuilder.build_workflow(name="Two Step", steps=steps)


async def test_execute_step_returns_the_task_result_directly():
    engine = _build_engine(
        {TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH, output={"found": 3})}
    )
    step = WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")

    result = await engine.execute_step(step, TaskContext())

    assert result.success is True
    assert result.output == {"found": 3}


async def test_execute_step_for_an_unregistered_task_type_raises():
    engine = _build_engine({})
    step = WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")

    with pytest.raises(TaskNotAvailableError):
        await engine.execute_step(step, TaskContext())


async def test_execute_workflow_happy_path_completes():
    engine = _build_engine(
        {
            TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH, output={"a": 1}),
            TaskType.QUALIFICATION: _SucceedingTask(TaskType.QUALIFICATION, output={"b": 2}),
            TaskType.COPY: _SucceedingTask(TaskType.COPY, output={"c": 3}),
        }
    )
    workflow = _two_step_workflow(continue_on_error=False)

    result = await engine.execute_workflow(workflow, TaskContext())

    assert result.success is True
    assert result.execution.status == WorkflowStatus.COMPLETED
    assert result.execution.completed_steps == [1, 2, 3]
    assert result.execution.failed_steps == []
    assert result.outputs == {
        "research": {"a": 1},
        "qualification": {"b": 2},
        "copy_generation": {"c": 3},
    }


async def test_failure_with_continue_on_error_false_pauses_and_stops():
    engine = _build_engine(
        {
            TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH),
            TaskType.QUALIFICATION: _FailingTask(
                TaskType.QUALIFICATION, error="score indisponível"
            ),
            TaskType.COPY: _SucceedingTask(TaskType.COPY),
        }
    )
    workflow = _two_step_workflow(continue_on_error=False)

    result = await engine.execute_workflow(workflow, TaskContext())

    assert result.success is False
    assert result.execution.status == WorkflowStatus.PAUSED
    assert result.execution.completed_steps == [1]
    assert result.execution.failed_steps == [2]
    assert result.execution.current_step == 2
    # the third step (copy_generation) never ran
    assert "copy_generation" not in result.outputs
    assert any("score indisponível" in error for error in result.errors)


async def test_failure_with_continue_on_error_true_continues_and_completes():
    engine = _build_engine(
        {
            TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH),
            TaskType.QUALIFICATION: _FailingTask(
                TaskType.QUALIFICATION, error="score indisponível"
            ),
            TaskType.COPY: _SucceedingTask(TaskType.COPY, output={"generated": True}),
        }
    )
    workflow = _two_step_workflow(continue_on_error=True)

    result = await engine.execute_workflow(workflow, TaskContext())

    assert result.execution.status == WorkflowStatus.COMPLETED
    assert result.success is False  # still had a failed step, even though it finished
    assert result.execution.completed_steps == [1, 3]
    assert result.execution.failed_steps == [2]
    assert result.outputs["copy_generation"] == {"generated": True}
    assert any("continue_on_error=True" in warning for warning in result.warnings)


async def test_step_timeout_produces_a_failed_task_result():
    engine = _build_engine({TaskType.RESEARCH: _SlowTask(TaskType.RESEARCH, delay=0.2)})
    step = WorkflowBuilder.build_step(
        order=1, task_type=TaskType.RESEARCH, name="research", timeout=0.01
    )

    result = await engine.execute_step(step, TaskContext())

    assert result.success is False
    assert any("timed out" in error for error in result.errors)


async def test_cancel_from_running_or_paused_transitions_to_cancelled():
    engine = _build_engine({TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH)})
    workflow = WorkflowBuilder.build_workflow(
        name="One Step",
        steps=[WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")],
    )
    result = await engine.execute_workflow(workflow, TaskContext())

    cancelled = engine.cancel(result.execution)

    assert cancelled.status == WorkflowStatus.CANCELLED
    assert cancelled.finished_at is not None


def test_cancel_a_pending_execution_raises():
    engine = _build_engine({})
    pending = WorkflowExecution(workflow_id=uuid.uuid4(), status=WorkflowStatus.PENDING)

    with pytest.raises(InvalidWorkflowTransitionError):
        engine.cancel(pending)


async def test_resume_skips_the_failed_step_and_continues():
    engine = _build_engine(
        {
            TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH),
            TaskType.QUALIFICATION: _FailingTask(TaskType.QUALIFICATION),
            TaskType.COPY: _SucceedingTask(TaskType.COPY, output={"generated": True}),
        }
    )
    workflow = _two_step_workflow(continue_on_error=False)
    engine.registry.register(workflow)
    paused = await engine.execute_workflow(workflow, TaskContext())
    assert paused.execution.status == WorkflowStatus.PAUSED

    resumed = await engine.resume(paused.execution, TaskContext())

    assert resumed.execution.status == WorkflowStatus.COMPLETED
    assert resumed.execution.completed_steps == [1, 3]
    assert resumed.execution.failed_steps == [2]
    assert resumed.outputs["copy_generation"] == {"generated": True}


async def test_retry_reattempts_the_failed_step():
    calls: list[int] = []

    class _FlakyTask(ApplicationTask):
        task_type: ClassVar[TaskType] = TaskType.QUALIFICATION
        name: ClassVar[str] = "flaky_task"

        def validate(self, context: TaskContext) -> None:
            pass

        async def execute(self, context: TaskContext) -> dict[str, Any]:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("transient failure")
            return {"score": 80}

        async def rollback(self, context: TaskContext) -> None:
            pass

    engine = _build_engine(
        {
            TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH),
            TaskType.QUALIFICATION: _FlakyTask(),
            TaskType.COPY: _SucceedingTask(TaskType.COPY, output={"generated": True}),
        }
    )
    workflow = _two_step_workflow(continue_on_error=False)
    engine.registry.register(workflow)
    paused = await engine.execute_workflow(workflow, TaskContext())
    assert paused.execution.status == WorkflowStatus.PAUSED

    retried = await engine.retry(paused.execution, TaskContext())

    assert retried.execution.status == WorkflowStatus.COMPLETED
    assert retried.execution.completed_steps == [1, 2, 3]
    assert retried.execution.failed_steps == []
    assert retried.success is True


async def test_resume_on_a_running_execution_raises():
    engine = _build_engine({TaskType.RESEARCH: _SucceedingTask(TaskType.RESEARCH)})
    running = WorkflowExecution(workflow_id=uuid.uuid4(), status=WorkflowStatus.RUNNING)

    with pytest.raises(InvalidWorkflowTransitionError):
        await engine.resume(running, TaskContext())
