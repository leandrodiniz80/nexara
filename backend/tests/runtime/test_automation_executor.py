import uuid

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.automation.models.automation_execution import AutomationExecution
from app.automation.models.enums import AutomationStatus
from app.automation.schemas.automation_request import AutomationRequest
from app.automation.schemas.automation_response import AutomationResponse
from app.runtime.exceptions.runtime_exceptions import MissingExecutionRequestError
from app.runtime.executors.automation_executor import AutomationExecutor
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution_context import ExecutionContext
from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow_execution import WorkflowExecution
from app.workflows.models.workflow_result import WorkflowResult
from app.workflows.schemas.workflow_request import WorkflowRequest


class _FakeAutomationEngine:
    """Satisfies exactly the shape AutomationExecutor relies on
    (`async def execute(request: AutomationRequest) -> AutomationResponse`) — not a
    real AutomationEngine, so these tests never touch WorkflowEngine/Task layers."""

    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.calls: list[AutomationRequest] = []

    async def execute(self, request: AutomationRequest) -> AutomationResponse:
        self.calls.append(request)
        workflow_execution = WorkflowExecution(
            workflow_id=uuid.uuid4(),
            status=WorkflowStatus.COMPLETED if self.success else WorkflowStatus.PAUSED,
        )
        workflow_result = WorkflowResult(
            success=self.success,
            execution=workflow_execution,
            outputs={"summary": "done"} if self.success else {},
            errors=[] if self.success else ["a step failed"],
            duration=0.01,
        )
        execution = AutomationExecution(
            automation_id=uuid.uuid4(),
            status=AutomationStatus.COMPLETED if self.success else AutomationStatus.FAILED,
            workflow_execution_id=workflow_execution.execution_id,
        )
        return AutomationResponse(execution=execution, workflow_result=workflow_result)


def _context(*, automation_request: AutomationRequest | None) -> ExecutionContext:
    return ExecutionContext(automation_request=automation_request)


def _automation_request() -> AutomationRequest:
    return AutomationRequest(
        automation_name="Test Automation",
        workflow_request=WorkflowRequest(workflow_name="Test Workflow", context=TaskContext()),
    )


async def test_execute_calls_the_automation_engine_and_returns_a_successful_result():
    fake = _FakeAutomationEngine(success=True)
    executor = AutomationExecutor(fake)
    request = _automation_request()

    result = await executor.execute(_context(automation_request=request))

    assert fake.calls == [request]
    assert result.success is True
    assert result.execution.execution_type == ExecutionType.AUTOMATION
    assert result.execution.status == ExecutionStatus.SUCCESS
    assert result.execution.started_at is not None
    assert result.execution.finished_at is not None
    assert result.payload == {"summary": "done"}
    assert result.errors == []


async def test_execute_reports_failed_status_when_workflow_result_is_unsuccessful():
    fake = _FakeAutomationEngine(success=False)
    executor = AutomationExecutor(fake)

    result = await executor.execute(_context(automation_request=_automation_request()))

    assert result.success is False
    assert result.execution.status == ExecutionStatus.FAILED
    assert result.errors == ["a step failed"]


async def test_execute_without_an_automation_request_raises():
    executor = AutomationExecutor(_FakeAutomationEngine())

    with pytest.raises(MissingExecutionRequestError):
        await executor.execute(_context(automation_request=None))


def test_supports_only_reports_true_for_automation():
    executor = AutomationExecutor(_FakeAutomationEngine())

    assert executor.supports(ExecutionType.AUTOMATION) is True
    assert executor.supports(ExecutionType.WORKFLOW) is False
    assert executor.supports(ExecutionType.JOB) is False


def test_automation_executor_never_imports_workflow_engine():
    """AutomationExecutor must only ever call AutomationEngine — never
    WorkflowEngine directly, even though that's what AutomationEngine itself calls
    underneath."""
    import app.runtime.executors.automation_executor as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    assert "WorkflowEngine" not in source
