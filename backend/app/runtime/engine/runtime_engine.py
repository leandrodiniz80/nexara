from datetime import datetime, timezone

from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operations_coordinator import OperationsCoordinator
from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult
from app.runtime.registry.executor_registry import ExecutorRegistry
from app.runtime.repositories.execution_repository import ExecutionRepository

_OPERATIONAL_FAILURE_REASON = "Operational failure."


class RuntimeEngine:
    """The single point responsible for executing any operation on the platform.
    Today that means Workflows and Automations; tomorrow it could mean Jobs,
    Pipelines, or Agents, without this class's own public API changing at all —
    adding support for a new ExecutionType is exactly one new Executor registered
    with `register_executor()`, never a new method here.

    This file never imports WorkflowEngine or AutomationEngine — it reaches them
    only indirectly, through whichever registered Executor's `execute()` happens to
    call one of them. RuntimeEngine itself only ever talks to ExecutorRegistry
    directly for dispatch.

    Every execution now passes through OperationsCoordinator first:
    RuntimeEngine knows OperationsCoordinator, but OperationsCoordinator never
    knows Runtime — the dependency is strictly one-directional. When
    OperationsCoordinator.run() reports `success=False`, that operational
    failure short-circuits before any Executor ever runs, and the resulting
    Execution never reaches ExecutionRepository — only a successful operation
    reaches an Executor and gets persisted.
    """

    def __init__(
        self,
        repository: ExecutionRepository,
        registry: ExecutorRegistry,
        operations_coordinator: OperationsCoordinator,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.operations_coordinator = operations_coordinator

    async def execute(
        self, execution_type: ExecutionType, context: ExecutionContext
    ) -> ExecutionResult:
        operation_result = self.operations_coordinator.run(
            OperationContext(
                operation_name=f"runtime_execute_{execution_type.value}",
                metadata={"execution_type": execution_type.value, **context.metadata},
            )
        )

        if not operation_result.success:
            now = datetime.now(timezone.utc)
            failed_execution = Execution(
                execution_type=execution_type,
                status=ExecutionStatus.FAILED,
                started_at=now,
                finished_at=now,
                duration=0.0,
            )
            return ExecutionResult(
                success=False,
                execution=failed_execution,
                errors=[operation_result.reason or _OPERATIONAL_FAILURE_REASON],
            )

        executor = self.registry.get(execution_type)
        result = await executor.execute(context)
        self.repository.save_execution(result.execution)
        return result

    async def execute_workflow(self, context: ExecutionContext) -> ExecutionResult:
        return await self.execute(ExecutionType.WORKFLOW, context)

    async def execute_automation(self, context: ExecutionContext) -> ExecutionResult:
        return await self.execute(ExecutionType.AUTOMATION, context)

    async def execute_job(self, context: ExecutionContext) -> ExecutionResult:
        return await self.execute(ExecutionType.JOB, context)

    def register_executor(self, executor: Executor) -> Executor:
        return self.registry.register(executor)
