import uuid
from datetime import datetime, timezone

import pytest

from app.application.execution.execution_service import (
    DEFAULT_PROSPECTING_WORKFLOW_NAME,
    ExecutionService,
)
from app.application.execution.execution_service_factory import build_default_execution_service
from app.bootstrap.bootstrap import Bootstrap
from app.bootstrap.container import ServiceNotRegisteredError
from app.bootstrap.module_loader import BootstrapModule
from app.config.settings import PlatformSettings
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_result import ExecutionResult
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead


class _FakeRuntimeEngine:
    """Satisfies exactly the shape ExecutionService relies on
    (`execute_workflow(context) -> ExecutionResult`) — lets these tests
    inspect precisely what ExecutionContext/WorkflowRequest/TaskContext
    ExecutionService assembled, without a real Workflow/Task chain."""

    def __init__(self, *, result: ExecutionResult | None = None, raises: Exception | None = None):
        self.result = result if result is not None else _execution_result()
        self.raises = raises
        self.calls = []

    async def execute_workflow(self, context):
        self.calls.append(context)
        if self.raises is not None:
            raise self.raises
        return self.result


def _execution_result() -> ExecutionResult:
    execution = Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.SUCCESS)
    return ExecutionResult(success=True, execution=execution, payload={"outputs": True})


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


async def test_execute_prospecting_assembles_the_expected_execution_context():
    runtime = _FakeRuntimeEngine()
    service = ExecutionService(runtime)
    mission_id = uuid.uuid4()

    await service.execute_prospecting(
        workflow_name="Custom Workflow", mission_id=mission_id, variables={"score": 80}
    )

    context = runtime.calls[0]
    assert context.mission_id == mission_id
    assert context.workflow_request.workflow_name == "Custom Workflow"
    assert context.workflow_request.context.mission_id == mission_id
    assert context.workflow_request.context.variables == {"score": 80}


async def test_execute_prospecting_uses_the_default_workflow_name_when_not_given():
    runtime = _FakeRuntimeEngine()
    service = ExecutionService(runtime)

    await service.execute_prospecting()

    assert runtime.calls[0].workflow_request.workflow_name == DEFAULT_PROSPECTING_WORKFLOW_NAME


async def test_execute_prospecting_defaults_variables_to_an_empty_dict():
    runtime = _FakeRuntimeEngine()
    service = ExecutionService(runtime)

    await service.execute_prospecting()

    assert runtime.calls[0].workflow_request.context.variables == {}


async def test_execute_prospecting_calls_runtime_execute_workflow_exactly_once():
    runtime = _FakeRuntimeEngine()
    service = ExecutionService(runtime)

    await service.execute_prospecting()

    assert len(runtime.calls) == 1


async def test_execute_prospecting_returns_the_runtime_result_untouched():
    result = _execution_result()
    runtime = _FakeRuntimeEngine(result=result)
    service = ExecutionService(runtime)

    returned = await service.execute_prospecting()

    assert returned is result


async def test_execute_prospecting_propagates_runtime_errors():
    """ExecutionService contains no business rule of its own — a Runtime
    failure must propagate exactly as RuntimeEngine raised it, never be
    caught or reinterpreted here."""
    runtime = _FakeRuntimeEngine(raises=RuntimeError("no such workflow"))
    service = ExecutionService(runtime)

    with pytest.raises(RuntimeError, match="no such workflow"):
        await service.execute_prospecting()


async def test_execute_prospecting_end_to_end_with_the_real_runtime_engine():
    """Compatibility with existing Runtime: the real build_default_runtime_engine()
    (unchanged by this sprint) runs the real "Prospecting Workflow" —
    ResearchTask -> QualificationTask -> CopyTask — exactly as it did before
    ExecutionService existed."""
    service = ExecutionService(build_default_runtime_engine())

    result = await service.execute_prospecting(
        variables={
            "strategy": "city",
            "query": {"city": "Goiânia"},
            "profile": CommercialProfile(segment="retail", company_size="small"),
            "company": _company(),
            "asset_type": "email",
        }
    )

    assert result.execution.execution_type == ExecutionType.WORKFLOW


def test_build_default_execution_service_routes_through_bootstrap():
    service = build_default_execution_service()

    assert isinstance(service, ExecutionService)
    assert isinstance(service.runtime_engine, RuntimeEngine)


def test_build_default_execution_service_reuses_a_given_bootstrap():
    bootstrap = Bootstrap(PlatformSettings(enabled_modules=["runtime"]))

    service = build_default_execution_service(bootstrap=bootstrap)

    assert bootstrap.is_initialized() is True
    assert service.runtime_engine is bootstrap.locator().get(RuntimeEngine)


def test_build_default_execution_service_initializes_a_not_yet_initialized_bootstrap():
    bootstrap = Bootstrap(PlatformSettings(enabled_modules=["runtime"]))
    assert bootstrap.is_initialized() is False

    build_default_execution_service(bootstrap=bootstrap)

    assert bootstrap.is_initialized() is True


def test_build_default_execution_service_does_not_reinitialize_an_already_initialized_bootstrap():
    bootstrap = Bootstrap(PlatformSettings(enabled_modules=["runtime"]))
    bootstrap.initialize()
    first_runtime_engine = bootstrap.locator().get(RuntimeEngine)

    service = build_default_execution_service(bootstrap=bootstrap)

    assert service.runtime_engine is first_runtime_engine


def test_build_default_execution_service_respects_runtime_disabled_in_settings():
    """Confirms this factory genuinely honors Configuration as the single
    source of truth: if Runtime is disabled, there is nothing to hand out."""
    bootstrap = Bootstrap(PlatformSettings(enabled_modules=[BootstrapModule.CRM.value]))

    with pytest.raises(ServiceNotRegisteredError):
        build_default_execution_service(bootstrap=bootstrap)
