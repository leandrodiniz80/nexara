import time
from datetime import datetime, timezone

from app.runtime.exceptions.runtime_exceptions import MissingExecutionRequestError
from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult
from app.workflows.engine.workflow_engine import WorkflowEngine


class WorkflowExecutor(Executor):
    """Receives a WorkflowRequest (via ExecutionContext.workflow_request), calls
    WorkflowEngine.execute(), and reports the outcome as an ExecutionResult. This
    is the *only* place in app/runtime that imports WorkflowEngine — RuntimeEngine
    itself never does, reaching it only through this Executor.
    """

    def __init__(self, workflow_engine: WorkflowEngine) -> None:
        self.workflow_engine = workflow_engine

    def supports(self, execution_type: ExecutionType) -> bool:
        return execution_type == ExecutionType.WORKFLOW

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        if context.workflow_request is None:
            raise MissingExecutionRequestError(ExecutionType.WORKFLOW)

        start = time.perf_counter()
        execution = Execution(
            execution_type=ExecutionType.WORKFLOW,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        workflow_response = await self.workflow_engine.execute(context.workflow_request)
        workflow_result = workflow_response.result

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
