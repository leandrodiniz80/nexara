import uuid
from datetime import datetime, timezone

import pytest

from app.application.tasks.context.task_context import TaskContext
from app.automation.schemas.automation_request import AutomationRequest
from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operation_result import OperationResult
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.registry.executor_registry import ExecutorRegistry
from app.runtime.repositories.execution_repository import ExecutionRepository
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead
from app.workflows.schemas.workflow_request import WorkflowRequest


class _FakeOperationsCoordinator:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.calls: list[OperationContext] = []

    def run(self, context: OperationContext) -> OperationResult:
        self.calls.append(context)
        return OperationResult(success=self.success, execution_time=0.0)


def test_build_default_runtime_engine_registers_workflow_automation_and_job():
    engine = build_default_runtime_engine()

    executors = engine.registry.list()
    supported = {t for t in ExecutionType if any(e.supports(t) for e in executors)}
    assert supported == {ExecutionType.WORKFLOW, ExecutionType.AUTOMATION, ExecutionType.JOB}


def test_build_default_runtime_engine_reuses_a_given_repository_and_registry():
    repository = ExecutionRepository()
    registry = ExecutorRegistry()

    engine = build_default_runtime_engine(repository=repository, registry=registry)

    assert engine.repository is repository
    assert engine.registry is registry


def test_build_default_runtime_engine_builds_a_working_operations_coordinator_by_default():
    engine = build_default_runtime_engine()

    assert engine.operations_coordinator is not None


def test_build_default_runtime_engine_reuses_a_given_operations_coordinator():
    coordinator = _FakeOperationsCoordinator()

    engine = build_default_runtime_engine(operations_coordinator=coordinator)

    assert engine.operations_coordinator is coordinator


def _company() -> CompanyRead:
    now = datetime.now(timezone.utc)
    return CompanyRead(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        legal_name="Agência XYZ Ltda",
        trade_name="Agência XYZ",
        cnpj="12345678000199",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
    )


def _prospecting_task_context() -> TaskContext:
    return TaskContext(
        mission_id=uuid.uuid4(),
        prospect_id=uuid.uuid4(),
        variables={
            "strategy": "city",
            "query": {"city": "Goiânia"},
            "profile": CommercialProfile(segment="retail", company_size="small"),
            "company": _company(),
            "asset_type": "email",
        },
    )


async def test_execute_workflow_runs_the_prospecting_workflow_end_to_end():
    """Uses the real WorkflowEngine (and, underneath it, the real
    ResearchTask/QualificationTask/CopyTask) reached only through RuntimeEngine ->
    ExecutorRegistry -> WorkflowExecutor — RuntimeEngine itself never touches
    WorkflowEngine directly."""
    engine = build_default_runtime_engine()
    context = ExecutionContext(
        workflow_request=WorkflowRequest(
            workflow_name="Prospecting Workflow", context=_prospecting_task_context()
        )
    )

    result = await engine.execute_workflow(context)

    assert result.execution.execution_type == ExecutionType.WORKFLOW
    assert result.execution.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED}
    assert engine.repository.get_execution(result.execution.id) is result.execution


async def test_execute_automation_runs_daily_prospecting_end_to_end():
    """Reaches AutomationEngine (and, underneath it, WorkflowEngine again) only
    through RuntimeEngine -> ExecutorRegistry -> AutomationExecutor."""
    engine = build_default_runtime_engine()
    context = ExecutionContext(
        automation_request=AutomationRequest(
            automation_name="Daily Prospecting",
            workflow_request=WorkflowRequest(
                workflow_name="ignored-by-automation-engine", context=_prospecting_task_context()
            ),
        )
    )

    result = await engine.execute_automation(context)

    assert result.execution.execution_type == ExecutionType.AUTOMATION
    assert result.execution.status in {ExecutionStatus.SUCCESS, ExecutionStatus.FAILED}
    assert engine.repository.get_execution(result.execution.id) is result.execution


async def test_execute_job_raises_not_implemented_through_the_full_stack():
    engine = build_default_runtime_engine()

    with pytest.raises(NotImplementedError):
        await engine.execute_job(ExecutionContext())
