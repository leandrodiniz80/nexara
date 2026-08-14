import inspect

from app.decision.models.decision_option import DecisionOption
from app.decision.models.decision_result import DecisionResult
from app.observability.models.execution_step import ExecutionStatus as ObservabilityStatus
from app.observability.models.execution_trace import ExecutionTrace
from app.operations.coordinator.operation_result import OperationResult
from app.platform.modules.module_registry import ModuleRegistry
from app.platform.modules.platform_module import PlatformModule
from app.platform.orchestration import platform_execution_orchestrator
from app.platform.orchestration import platform_execution_orchestrator_factory
from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.orchestration.platform_execution_orchestrator import (
    PlatformExecutionOrchestrator,
)
from app.platform.orchestration.platform_execution_orchestrator_factory import (
    build_default_platform_execution_orchestrator,
)
from app.platform.pipeline.execution_pipeline import ExecutionPipeline
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_provider import StageProvider
from app.platform.session.execution_session import ExecutionSession
from app.platform.session.execution_session_service import ExecutionSessionService
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult


def _payload() -> tuple:
    return (ExecutionType.WORKFLOW, ExecutionContext())


class _FakeExecutionPipeline:
    def __init__(self, *, state: dict | None = None) -> None:
        self._state = state or {}
        self.calls = 0
        self.received_session: ExecutionSession | None = None
        self.received_context: PlatformExecutionContext | None = None

    async def execute(self, session, context):
        self.calls += 1
        self.received_session = session
        self.received_context = context
        return dict(self._state)


def _orchestrator(
    *, state: dict | None = None
) -> tuple[PlatformExecutionOrchestrator, _FakeExecutionPipeline, ExecutionSessionService]:
    pipeline = _FakeExecutionPipeline(state=state)
    session_service = ExecutionSessionService()
    orchestrator = PlatformExecutionOrchestrator(
        execution_pipeline=pipeline, execution_session_service=session_service
    )
    return orchestrator, pipeline, session_service


async def test_orchestrator_delegates_to_the_pipeline_exactly_once():
    orchestrator, pipeline, _ = _orchestrator()
    context = PlatformExecutionContext(payload=_payload())

    await orchestrator.execute(context)

    assert pipeline.calls == 1


def _operation_result() -> OperationResult:
    return OperationResult(success=True, execution_time=0.1, history=None)


def _decision_result() -> DecisionResult:
    return DecisionResult(
        selected_option=DecisionOption(name="proceed", score=1.0),
        candidate_options=[],
        execution_time=0.1,
        success=True,
    )


def _runtime_result() -> ExecutionResult:
    execution = Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.SUCCESS)
    return ExecutionResult(success=True, execution=execution)


def _observability_result() -> ExecutionTrace:
    return ExecutionTrace(execution_type="operation", status=ObservabilityStatus.SUCCESS)


async def test_orchestrator_reads_success_and_results_from_the_pipeline_state():
    operation_result = _operation_result()
    decision_result = _decision_result()
    runtime_result = _runtime_result()
    observability_result = _observability_result()
    state = {
        "success": True,
        "operation_result": operation_result,
        "decision_result": decision_result,
        "runtime_result": runtime_result,
        "observability_result": observability_result,
    }
    orchestrator, _, _ = _orchestrator(state=state)
    context = PlatformExecutionContext(payload=_payload())

    result = await orchestrator.execute(context)

    assert result.success is True
    assert result.operation_result is operation_result
    assert result.decision_result is decision_result
    assert result.runtime_result is runtime_result
    assert result.observability_result is observability_result


async def test_orchestrator_defaults_success_to_true_when_absent_from_state():
    orchestrator, _, _ = _orchestrator(state={})
    context = PlatformExecutionContext(payload=_payload())

    result = await orchestrator.execute(context)

    assert result.success is True


async def test_orchestrator_reports_failure_from_the_pipeline_state():
    orchestrator, _, _ = _orchestrator(state={"success": False})
    context = PlatformExecutionContext(payload=_payload())

    result = await orchestrator.execute(context)

    assert result.success is False


async def test_execution_session_preservada_between_create_and_pipeline():
    orchestrator, pipeline, _ = _orchestrator()
    context = PlatformExecutionContext(payload=_payload())

    result = await orchestrator.execute(context)

    assert pipeline.received_session is not None
    assert result.execution_session.session_id == pipeline.received_session.session_id
    assert result.execution_session.finished_at is not None


async def test_request_id_preservado_in_the_result_and_session():
    orchestrator, _, _ = _orchestrator()
    context = PlatformExecutionContext(request_id="req-1", payload=_payload())

    result = await orchestrator.execute(context)

    assert result.request_id == "req-1"
    assert result.execution_session.request_id == "req-1"


def test_injecao_uses_exactly_the_collaborators_provided():
    orchestrator, pipeline, session_service = _orchestrator()

    assert orchestrator._execution_pipeline is pipeline
    assert orchestrator._execution_session_service is session_service


def test_build_default_platform_execution_orchestrator_returns_a_usable_orchestrator():
    orchestrator = build_default_platform_execution_orchestrator()

    assert isinstance(orchestrator, PlatformExecutionOrchestrator)
    assert isinstance(orchestrator._execution_pipeline, ExecutionPipeline)
    assert isinstance(orchestrator._execution_session_service, ExecutionSessionService)


def test_build_default_platform_execution_orchestrator_reuses_given_collaborators():
    pipeline = ExecutionPipeline([])
    session_service = ExecutionSessionService()

    orchestrator = build_default_platform_execution_orchestrator(
        execution_pipeline=pipeline, execution_session_service=session_service
    )

    assert orchestrator._execution_pipeline is pipeline
    assert orchestrator._execution_session_service is session_service


def test_orchestrator_conhece_apenas_pipeline_e_session_service():
    """PlatformExecutionOrchestrator no longer imports any domain module —
    only ExecutionPipeline and ExecutionSessionService, both internal to
    app.platform.
    """
    source = inspect.getsource(platform_execution_orchestrator)
    assert "app.operations" not in source
    assert "app.decision" not in source
    assert "app.runtime" not in source
    assert "app.observability" not in source


def test_nenhum_import_de_crm():
    source = inspect.getsource(platform_execution_orchestrator)
    assert "app.crm" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(platform_execution_orchestrator)
    assert "app.workflows" not in source


def test_nenhum_import_de_decision():
    source = inspect.getsource(platform_execution_orchestrator)
    assert "app.decision" not in source


def test_nenhum_import_de_observability():
    source = inspect.getsource(platform_execution_orchestrator)
    assert "app.observability" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(platform_execution_orchestrator)
    assert "app.runtime" not in source


class _EmptyStageProvider(StageProvider):
    def stages(self) -> tuple[PipelineStage, ...]:
        return ()


class _FakeModule(PlatformModule):
    def __init__(self, module_name: str) -> None:
        self._name = module_name

    def name(self) -> str:
        return self._name

    def stage_provider(self) -> StageProvider:
        return _EmptyStageProvider()


def test_build_default_platform_execution_orchestrator_uses_the_given_module_registry():
    registry = ModuleRegistry().register(_FakeModule("default"))

    orchestrator = build_default_platform_execution_orchestrator(module_registry=registry)

    assert isinstance(orchestrator, PlatformExecutionOrchestrator)
    assert isinstance(orchestrator._execution_pipeline, ExecutionPipeline)
    assert orchestrator._execution_pipeline.list_stages() == []


def test_orchestrator_factory_conhece_apenas_module_registry():
    source = inspect.getsource(platform_execution_orchestrator_factory)
    assert "ModuleRegistry" in source


def test_orchestrator_factory_nenhuma_referencia_a_stage_provider():
    source = inspect.getsource(platform_execution_orchestrator_factory)
    assert "StageProvider" not in source
