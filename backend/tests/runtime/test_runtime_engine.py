import pytest

from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operation_result import OperationResult
from app.operations.coordinator.operations_coordinator import OperationsCoordinator
from app.operations.services.operations_engine_factory import build_default_operations_engine
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.exceptions.runtime_exceptions import ExecutorNotFoundError
from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult
from app.runtime.registry.executor_registry import ExecutorRegistry
from app.runtime.repositories.execution_repository import ExecutionRepository


class _FakeExecutor(Executor):
    """Returns a fixed ExecutionResult for one ExecutionType — enough to exercise
    RuntimeEngine's dispatch-and-persist flow without any real Workflow/Automation
    engine involved."""

    def __init__(self, execution_type: ExecutionType, *, success: bool = True) -> None:
        self.execution_type = execution_type
        self.success = success
        self.calls: list[ExecutionContext] = []

    def supports(self, execution_type: ExecutionType) -> bool:
        return execution_type == self.execution_type

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        self.calls.append(context)
        execution = Execution(
            execution_type=self.execution_type,
            status=ExecutionStatus.SUCCESS if self.success else ExecutionStatus.FAILED,
        )
        return ExecutionResult(success=self.success, execution=execution)


class _FakeOperationsCoordinator:
    """A stand-in for OperationsCoordinator that never touches the real
    Operations domain — enough to exercise RuntimeEngine's own branching on
    OperationResult.success without depending on OperationsEngine's real
    behavior."""

    def __init__(self, *, success: bool = True, reason: str | None = None) -> None:
        self.success = success
        self.reason = reason
        self.calls: list[OperationContext] = []

    def run(self, context: OperationContext) -> OperationResult:
        self.calls.append(context)
        return OperationResult(success=self.success, reason=self.reason, execution_time=0.0)


def _build_engine(
    *executors: Executor, operations_coordinator: OperationsCoordinator | None = None
) -> tuple[RuntimeEngine, ExecutionRepository]:
    registry = ExecutorRegistry()
    for executor in executors:
        registry.register(executor)
    repository = ExecutionRepository()
    coordinator = operations_coordinator or _FakeOperationsCoordinator()
    engine = RuntimeEngine(
        repository=repository, registry=registry, operations_coordinator=coordinator
    )
    return engine, repository


async def test_execute_dispatches_to_the_executor_that_supports_the_type():
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    engine, _ = _build_engine(executor)
    context = ExecutionContext()

    result = await engine.execute(ExecutionType.WORKFLOW, context)

    assert executor.calls == [context]
    assert result.success is True


async def test_execute_persists_the_execution_in_the_repository():
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    engine, repository = _build_engine(executor)

    result = await engine.execute(ExecutionType.WORKFLOW, ExecutionContext())

    assert repository.get_execution(result.execution.id) is result.execution


async def test_execute_for_an_unregistered_type_raises_executor_not_found():
    engine, _ = _build_engine(_FakeExecutor(ExecutionType.WORKFLOW))

    with pytest.raises(ExecutorNotFoundError):
        await engine.execute(ExecutionType.AUTOMATION, ExecutionContext())


async def test_execute_workflow_delegates_to_execute_with_workflow_type():
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    engine, _ = _build_engine(executor)

    await engine.execute_workflow(ExecutionContext())

    assert executor.calls[0].workflow_request is None


async def test_execute_automation_delegates_to_execute_with_automation_type():
    executor = _FakeExecutor(ExecutionType.AUTOMATION)
    engine, _ = _build_engine(executor)

    result = await engine.execute_automation(ExecutionContext())

    assert result.execution.execution_type == ExecutionType.AUTOMATION


async def test_execute_job_delegates_to_execute_with_job_type():
    executor = _FakeExecutor(ExecutionType.JOB)
    engine, _ = _build_engine(executor)

    result = await engine.execute_job(ExecutionContext())

    assert result.execution.execution_type == ExecutionType.JOB


def test_register_executor_adds_it_to_the_registry():
    engine, _ = _build_engine()
    executor = _FakeExecutor(ExecutionType.WORKFLOW)

    engine.register_executor(executor)

    assert engine.registry.list() == [executor]


async def test_operations_coordinator_e_chamado_exatamente_uma_vez():
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    coordinator = _FakeOperationsCoordinator()
    engine, _ = _build_engine(executor, operations_coordinator=coordinator)

    await engine.execute(ExecutionType.WORKFLOW, ExecutionContext())

    assert len(coordinator.calls) == 1


async def test_falha_operacional_interrompe_execucao_antes_do_executor():
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    coordinator = _FakeOperationsCoordinator(success=False, reason="Operations engine is down.")
    engine, repository = _build_engine(executor, operations_coordinator=coordinator)

    result = await engine.execute(ExecutionType.WORKFLOW, ExecutionContext())

    assert result.success is False
    assert result.execution.status == ExecutionStatus.FAILED
    assert result.errors == ["Operations engine is down."]
    assert executor.calls == []
    assert repository.list_executions() == []


async def test_sucesso_operacional_continua_execucao_ate_o_executor():
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    coordinator = _FakeOperationsCoordinator(success=True)
    engine, repository = _build_engine(executor, operations_coordinator=coordinator)

    result = await engine.execute(ExecutionType.WORKFLOW, ExecutionContext())

    assert result.success is True
    assert executor.calls != []
    assert repository.get_execution(result.execution.id) is result.execution


async def test_falha_operacional_com_o_operations_coordinator_real():
    """OperationsCoordinator.run() itself never raises and always returns
    success=True for a freshly built OperationsEngine — this confirms
    RuntimeEngine's success path also works end to end against the real
    Operations domain, not just the fake."""
    executor = _FakeExecutor(ExecutionType.WORKFLOW)
    real_coordinator = OperationsCoordinator(build_default_operations_engine())
    engine, _ = _build_engine(executor, operations_coordinator=real_coordinator)

    result = await engine.execute(ExecutionType.WORKFLOW, ExecutionContext())

    assert result.success is True


def test_injecao_uses_exactly_the_operations_coordinator_provided():
    coordinator = _FakeOperationsCoordinator()
    registry = ExecutorRegistry()
    repository = ExecutionRepository()

    engine = RuntimeEngine(
        repository=repository, registry=registry, operations_coordinator=coordinator
    )

    assert engine.operations_coordinator is coordinator


def test_runtime_engine_module_never_imports_workflow_or_automation_engine():
    """RuntimeEngine reaches WorkflowEngine/AutomationEngine only indirectly,
    through whichever registered Executor's execute() calls one of them — this
    file itself must never import either engine directly, nor CRM."""
    import app.runtime.engine.runtime_engine as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    assert "from app.workflows" not in source
    assert "from app.automation" not in source
    assert "WorkflowEngine" not in source
    assert "AutomationEngine" not in source
    assert "app.crm" not in source
