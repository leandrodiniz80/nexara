import uuid

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.runtime.exceptions.runtime_exceptions import MissingExecutionRequestError
from app.runtime.executors.workflow_executor import WorkflowExecutor
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution_context import ExecutionContext
from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow_execution import WorkflowExecution
from app.workflows.models.workflow_result import WorkflowResult
from app.workflows.schemas.workflow_request import WorkflowRequest
from app.workflows.schemas.workflow_response import WorkflowResponse


class _FakeWorkflowEngine:
    """Satisfies exactly the shape WorkflowExecutor relies on
    (`async def execute(request: WorkflowRequest) -> WorkflowResponse`) — not a
    real WorkflowEngine, so these tests stay isolated from the Task layer."""

    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.calls: list[WorkflowRequest] = []

    async def execute(self, request: WorkflowRequest) -> WorkflowResponse:
        self.calls.append(request)
        execution = WorkflowExecution(
            workflow_id=uuid.uuid4(),
            status=WorkflowStatus.COMPLETED if self.success else WorkflowStatus.PAUSED,
        )
        result = WorkflowResult(
            success=self.success,
            execution=execution,
            outputs={"summary": "done"} if self.success else {},
            errors=[] if self.success else ["a step failed"],
            duration=0.01,
        )
        return WorkflowResponse(result=result)


def _context(*, workflow_request: WorkflowRequest | None) -> ExecutionContext:
    return ExecutionContext(workflow_request=workflow_request)


def _workflow_request() -> WorkflowRequest:
    return WorkflowRequest(workflow_name="Test Workflow", context=TaskContext())


async def test_execute_calls_the_workflow_engine_and_returns_a_successful_result():
    fake = _FakeWorkflowEngine(success=True)
    executor = WorkflowExecutor(fake)
    request = _workflow_request()

    result = await executor.execute(_context(workflow_request=request))

    assert fake.calls == [request]
    assert result.success is True
    assert result.execution.execution_type == ExecutionType.WORKFLOW
    assert result.execution.status == ExecutionStatus.SUCCESS
    assert result.execution.started_at is not None
    assert result.execution.finished_at is not None
    assert result.execution.duration is not None
    assert result.payload == {"summary": "done"}
    assert result.errors == []


async def test_execute_reports_failed_status_when_workflow_result_is_unsuccessful():
    fake = _FakeWorkflowEngine(success=False)
    executor = WorkflowExecutor(fake)

    result = await executor.execute(_context(workflow_request=_workflow_request()))

    assert result.success is False
    assert result.execution.status == ExecutionStatus.FAILED
    assert result.errors == ["a step failed"]


async def test_execute_without_a_workflow_request_raises():
    executor = WorkflowExecutor(_FakeWorkflowEngine())

    with pytest.raises(MissingExecutionRequestError):
        await executor.execute(_context(workflow_request=None))


def test_supports_only_reports_true_for_workflow():
    executor = WorkflowExecutor(_FakeWorkflowEngine())

    assert executor.supports(ExecutionType.WORKFLOW) is True
    assert executor.supports(ExecutionType.AUTOMATION) is False
    assert executor.supports(ExecutionType.JOB) is False
