from app.automation.engine.automation_engine import AutomationEngine
from app.automation.services.automation_engine_factory import build_default_automation_engine
from app.operations.coordinator.operations_coordinator import OperationsCoordinator
from app.operations.coordinator.operations_coordinator_factory import (
    build_default_operations_coordinator,
)
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.executors.automation_executor import AutomationExecutor
from app.runtime.executors.job_executor import JobExecutor
from app.runtime.executors.workflow_executor import WorkflowExecutor
from app.runtime.registry.executor_registry import ExecutorRegistry
from app.runtime.repositories.execution_repository import ExecutionRepository
from app.workflows.engine.workflow_engine import WorkflowEngine
from app.workflows.services.workflow_engine_factory import build_default_workflow_engine


def build_default_runtime_engine(
    *,
    repository: ExecutionRepository | None = None,
    registry: ExecutorRegistry | None = None,
    workflow_engine: WorkflowEngine | None = None,
    automation_engine: AutomationEngine | None = None,
    operations_coordinator: OperationsCoordinator | None = None,
) -> RuntimeEngine:
    """Composition root for this module — the *only* place in app/runtime that
    imports WorkflowEngine's and AutomationEngine's own factories (which are
    themselves what pull in every Task/AI/Outreach/Research/SalesIntelligence
    dependency several layers down). RuntimeEngine itself never sees any of that;
    it only receives the three Executors already wired to their engines.

    Also the only place in app/runtime that imports OperationsCoordinator's own
    factory — `build_default_operations_coordinator()` — used whenever a caller
    doesn't provide one, so RuntimeEngine always has a working operational
    coordination point without every caller needing to wire one by hand.
    """
    registry = registry or ExecutorRegistry()
    workflow_engine = workflow_engine or build_default_workflow_engine()
    automation_engine = automation_engine or build_default_automation_engine()
    operations_coordinator = operations_coordinator or build_default_operations_coordinator()

    registry.register(WorkflowExecutor(workflow_engine))
    registry.register(AutomationExecutor(automation_engine))
    registry.register(JobExecutor())

    return RuntimeEngine(
        repository=repository or ExecutionRepository(),
        registry=registry,
        operations_coordinator=operations_coordinator,
    )
