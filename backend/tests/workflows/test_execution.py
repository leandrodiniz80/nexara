import uuid
from typing import Any, ClassVar

from app.application.tasks.base.application_task import ApplicationTask, TaskType
from app.application.tasks.context.task_context import TaskContext
from app.application.tasks.executors.task_executor import TaskExecutor
from app.workflows.builders.workflow_builder import WorkflowBuilder
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow_execution import WorkflowExecution
from app.workflows.registry.workflow_registry import WorkflowRegistry
from app.workflows.repositories.workflow_repository import WorkflowRepository


class _EchoTask(ApplicationTask):
    name: ClassVar[str] = "echo_task"

    def __init__(self, task_type: TaskType) -> None:
        self.task_type = task_type

    def validate(self, context: TaskContext) -> None:
        pass

    async def execute(self, context: TaskContext) -> dict[str, Any]:
        return {"ran": self.task_type.value}

    async def rollback(self, context: TaskContext) -> None:
        pass


def test_workflow_execution_starts_pending_by_default():
    execution = WorkflowExecution(workflow_id=uuid.uuid4())

    assert execution.status == WorkflowStatus.PENDING
    assert execution.current_step is None
    assert execution.completed_steps == []
    assert execution.failed_steps == []
    assert execution.finished_at is None


def test_each_execution_id_is_unique():
    first = WorkflowExecution(workflow_id=uuid.uuid4())
    second = WorkflowExecution(workflow_id=uuid.uuid4())

    assert first.execution_id != second.execution_id


async def test_repository_stores_every_execution_of_the_same_workflow_separately():
    repository = WorkflowRepository()
    registry = WorkflowRegistry()
    engine = WorkflowEngine(
        repository=repository,
        registry=registry,
        tasks={TaskType.RESEARCH: _EchoTask(TaskType.RESEARCH)},
        task_executor=TaskExecutor(),
    )
    workflow = WorkflowBuilder.build_workflow(
        name="One Step",
        steps=[WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")],
    )
    registry.register(workflow)

    first = await engine.execute_workflow(workflow, TaskContext())
    second = await engine.execute_workflow(workflow, TaskContext())

    assert first.execution.execution_id != second.execution.execution_id
    stored = repository.list_executions(workflow_id=workflow.id)
    assert len(stored) == 2
    assert {e.execution_id for e in stored} == {
        first.execution.execution_id,
        second.execution.execution_id,
    }


async def test_repository_list_executions_filters_by_status():
    repository = WorkflowRepository()
    registry = WorkflowRegistry()
    engine = WorkflowEngine(
        repository=repository,
        registry=registry,
        tasks={TaskType.RESEARCH: _EchoTask(TaskType.RESEARCH)},
        task_executor=TaskExecutor(),
    )
    workflow = WorkflowBuilder.build_workflow(
        name="One Step",
        steps=[WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")],
    )
    registry.register(workflow)

    result = await engine.execute_workflow(workflow, TaskContext())
    # a still-RUNNING execution, constructed directly rather than via
    # execute_workflow() (which always runs synchronously to completion in these
    # tests) — just to exercise cancel() -> repository filtering.
    still_running = WorkflowExecution(workflow_id=workflow.id, status=WorkflowStatus.RUNNING)
    repository.save_execution(still_running)
    engine.cancel(still_running)

    completed = repository.list_executions(status=WorkflowStatus.COMPLETED)
    cancelled = repository.list_executions(status=WorkflowStatus.CANCELLED)

    assert result.execution.execution_id in {e.execution_id for e in completed}
    assert len(cancelled) == 1


async def test_result_duration_is_non_negative():
    engine = WorkflowEngine(
        repository=WorkflowRepository(),
        registry=WorkflowRegistry(),
        tasks={TaskType.RESEARCH: _EchoTask(TaskType.RESEARCH)},
        task_executor=TaskExecutor(),
    )
    workflow = WorkflowBuilder.build_workflow(
        name="One Step",
        steps=[WorkflowBuilder.build_step(order=1, task_type=TaskType.RESEARCH, name="research")],
    )

    result = await engine.execute_workflow(workflow, TaskContext())

    assert result.duration >= 0
