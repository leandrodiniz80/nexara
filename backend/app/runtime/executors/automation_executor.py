import time
from datetime import datetime, timezone

from app.automation.engine.automation_engine import AutomationEngine
from app.runtime.exceptions.runtime_exceptions import MissingExecutionRequestError
from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult


class AutomationExecutor(Executor):
    """Receives an AutomationRequest (via ExecutionContext.automation_request) and
    calls AutomationEngine.execute() — never WorkflowEngine directly, even though
    that's what AutomationEngine itself calls underneath. This is the *only* place
    in app/runtime that imports AutomationEngine — RuntimeEngine itself never does.
    """

    def __init__(self, automation_engine: AutomationEngine) -> None:
        self.automation_engine = automation_engine

    def supports(self, execution_type: ExecutionType) -> bool:
        return execution_type == ExecutionType.AUTOMATION

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        if context.automation_request is None:
            raise MissingExecutionRequestError(ExecutionType.AUTOMATION)

        start = time.perf_counter()
        execution = Execution(
            execution_type=ExecutionType.AUTOMATION,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        automation_response = await self.automation_engine.execute(context.automation_request)
        workflow_result = automation_response.workflow_result

        execution.status = (
            ExecutionStatus.SUCCESS if workflow_result.success else ExecutionStatus.FAILED
        )
        execution.finished_at = datetime.now(timezone.utc)
        execution.duration = time.perf_counter() - start

        return ExecutionResult(
            success=workflow_result.success,
            execution=execution,
            payload=workflow_result.outputs,
            warnings=workflow_result.warnings,
            errors=workflow_result.errors,
        )
