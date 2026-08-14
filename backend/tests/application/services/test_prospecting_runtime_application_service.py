import uuid
from datetime import datetime, timezone

from app.application.execution.execution_processing_result import ExecutionProcessingResult
from app.application.execution.execution_result_processor import ExecutionResultProcessor
from app.application.execution.execution_service import ExecutionService
from app.application.services.prospecting_runtime_application_service import (
    DEFAULT_WORKFLOW_NAME,
    ProspectingRuntimeApplicationService,
)
from app.application.services.prospecting_runtime_application_service_factory import (
    build_default_prospecting_runtime_application_service,
)
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.integration.adapters.crm_adapter import CRMAdapter
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter
from app.models.prospecting.enums import ProspectStage, ProspectStatus, ProspectTemperature
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_result import ExecutionResult
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.prospect import ProspectRead


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


def _prospect() -> ProspectRead:
    now = datetime.now(timezone.utc)
    return ProspectRead(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        company_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        mission_id=uuid.uuid4(),
        status=ProspectStatus.OPEN,
        temperature=ProspectTemperature.WARM,
        current_stage=ProspectStage.QUALIFIED,
    )


def _prospecting_variables(*, with_prospect: bool = False) -> dict:
    variables = {
        "strategy": "city",
        "query": {"city": "Goiânia"},
        "profile": CommercialProfile(segment="retail", company_size="small"),
        "company": _company(),
        "asset_type": "email",
    }
    if with_prospect:
        variables["prospect"] = _prospect()
    return variables


def _execution_result(*, success: bool = True, warnings=None, errors=None) -> ExecutionResult:
    execution = Execution(
        execution_type=ExecutionType.WORKFLOW,
        status=ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED,
    )
    return ExecutionResult(
        success=success,
        execution=execution,
        payload={"qualification": {"score": 80}},
        warnings=warnings or [],
        errors=errors or [],
    )


class _FakeExecutionService:
    """Satisfies exactly the shape ProspectingRuntimeApplicationService relies
    on (`execute_prospecting(*, workflow_name, mission_id, variables) ->
    ExecutionResult`)."""

    def __init__(self, *, result: ExecutionResult | None = None, raises: Exception | None = None):
        self.result = result if result is not None else _execution_result()
        self.raises = raises
        self.calls = []

    async def execute_prospecting(self, *, workflow_name, mission_id, variables):
        self.calls.append(
            {"workflow_name": workflow_name, "mission_id": mission_id, "variables": variables}
        )
        if self.raises is not None:
            raise self.raises
        return self.result


class _FakeExecutionResultProcessor:
    """Satisfies exactly the shape ProspectingRuntimeApplicationService relies
    on (`process(execution_result, *, company, prospect, variables) ->
    ExecutionProcessingResult`)."""

    def __init__(self, *, opportunity=None):
        self.opportunity = opportunity
        self.calls = []

    def process(self, execution_result, *, company, prospect, variables):
        self.calls.append(
            {
                "execution_result": execution_result,
                "company": company,
                "prospect": prospect,
                "variables": variables,
            }
        )
        return ExecutionProcessingResult(
            execution_result=execution_result,
            crm_opportunity=self.opportunity,
            warnings=list(execution_result.warnings),
            errors=list(execution_result.errors),
            execution_time=0.001,
        )


class _FakeDecisionAdapter:
    def __init__(self, *, chosen=None, raises: Exception | None = None):
        self.chosen = chosen
        self.raises = raises

    def choose_workflow(self, variables):
        if self.raises is not None:
            raise self.raises
        return self.chosen


class _FakeRulesAdapter:
    def __init__(self, *, eligible: bool = True, raises: Exception | None = None):
        self.eligible = eligible
        self.raises = raises

    def is_eligible(self, variables):
        if self.raises is not None:
            raise self.raises
        return self.eligible


class _FakeObservabilityAdapter:
    def __init__(self, *, raises: Exception | None = None):
        self.raises = raises
        self.calls = []

    def record(self, *, operation, execution_time, success):
        self.calls.append((operation, success))
        if self.raises is not None:
            raise self.raises


async def test_success_end_to_end_with_real_execution_service_and_processor():
    """Uses the real ExecutionService (wrapping the real RuntimeEngine, and
    underneath it, the real WorkflowEngine -> TaskExecutor ->
    ResearchTask/QualificationTask/CopyTask chain) and the real
    ExecutionResultProcessor (wrapping a real CRMEngine) — proving the whole
    chain still works with this service knowing nothing about CRM directly.
    """
    service = ProspectingRuntimeApplicationService(
        execution_service=ExecutionService(build_default_runtime_engine()),
        execution_result_processor=ExecutionResultProcessor(
            CRMAdapter(build_default_crm_engine())
        ),
        observability_adapter=ObservabilityAdapter(build_default_observability_engine()),
    )

    result = await service.run_prospecting(
        variables=_prospecting_variables(with_prospect=True)
    )

    assert result.success is True
    response = result.data
    assert response.execution_result.execution.execution_type == ExecutionType.WORKFLOW
    assert response.crm_opportunity is not None
    assert response.crm_opportunity.title == "Prospecting - Agência XYZ"
    assert response.execution_time >= 0


async def test_execution_without_any_adapter_still_succeeds():
    execution_service = _FakeExecutionService()
    processor = _FakeExecutionResultProcessor()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service, execution_result_processor=processor
    )

    result = await service.run_prospecting()

    assert result.success is True
    assert execution_service.calls[0]["workflow_name"] == DEFAULT_WORKFLOW_NAME
    assert result.data.crm_opportunity is None


async def test_company_and_prospect_are_extracted_from_variables_and_passed_to_the_processor():
    execution_service = _FakeExecutionService()
    processor = _FakeExecutionResultProcessor(opportunity="an-opportunity")
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service, execution_result_processor=processor
    )
    variables = _prospecting_variables(with_prospect=True)

    result = await service.run_prospecting(variables=variables)

    assert processor.calls[0]["company"] == variables["company"]
    assert processor.calls[0]["prospect"] == variables["prospect"]
    assert result.data.crm_opportunity == "an-opportunity"


async def test_runtime_failing_marks_the_whole_result_unsuccessful():
    execution_service = _FakeExecutionService(raises=RuntimeError("no such workflow"))
    processor = _FakeExecutionResultProcessor()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service, execution_result_processor=processor
    )

    result = await service.run_prospecting()

    assert result.success is False
    assert any("no such workflow" in error for error in result.errors)
    assert result.data is None
    assert processor.calls == []


async def test_observability_unavailable_is_downgraded_to_a_warning():
    execution_service = _FakeExecutionService()
    processor = _FakeExecutionResultProcessor()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service,
        execution_result_processor=processor,
        observability_adapter=_FakeObservabilityAdapter(raises=ConnectionError("obs down")),
    )

    result = await service.run_prospecting()

    assert result.success is True
    assert any("ObservabilityAdapter" in warning for warning in result.data.warnings)


async def test_decision_disabled_uses_the_default_workflow():
    execution_service = _FakeExecutionService()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service,
        execution_result_processor=_FakeExecutionResultProcessor(),
        decision_adapter=None,
    )

    result = await service.run_prospecting()

    assert result.success is True
    assert execution_service.calls[0]["workflow_name"] == DEFAULT_WORKFLOW_NAME


async def test_decision_enabled_overrides_the_default_workflow():
    execution_service = _FakeExecutionService()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service,
        execution_result_processor=_FakeExecutionResultProcessor(),
        decision_adapter=_FakeDecisionAdapter(chosen="Proposal Workflow"),
    )

    await service.run_prospecting()

    assert execution_service.calls[0]["workflow_name"] == "Proposal Workflow"


async def test_business_rules_disabled_skips_the_eligibility_check():
    execution_service = _FakeExecutionService()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service,
        execution_result_processor=_FakeExecutionResultProcessor(),
        rules_adapter=None,
    )

    result = await service.run_prospecting()

    assert result.success is True
    assert len(execution_service.calls) == 1


async def test_business_rules_blocking_marks_the_whole_result_unsuccessful():
    execution_service = _FakeExecutionService()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service,
        execution_result_processor=_FakeExecutionResultProcessor(),
        rules_adapter=_FakeRulesAdapter(eligible=False),
    )

    result = await service.run_prospecting()

    assert result.success is False
    assert execution_service.calls == []
    assert any("not eligible" in error for error in result.errors)


async def test_warnings_from_decision_and_rules_are_merged_with_the_processors_own_warnings():
    execution_service = _FakeExecutionService()
    service = ProspectingRuntimeApplicationService(
        execution_service=execution_service,
        execution_result_processor=_FakeExecutionResultProcessor(),
        decision_adapter=_FakeDecisionAdapter(raises=RuntimeError("decision boom")),
        rules_adapter=_FakeRulesAdapter(raises=RuntimeError("rules boom")),
    )

    result = await service.run_prospecting()

    assert result.success is True
    assert any("RulesAdapter" in warning for warning in result.data.warnings)
    assert any("DecisionAdapter" in warning for warning in result.data.warnings)


def test_service_has_no_knowledge_of_runtime_or_crm_internals():
    """Sprint 31/32's actual guarantee: this file must not reference
    WorkflowRequest, TaskContext, ExecutionContext, RuntimeEngine, or CRM
    types at all — that encapsulation now belongs entirely to
    ExecutionService and ExecutionResultProcessor respectively."""
    import app.application.services.prospecting_runtime_application_service as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    assert "from app.workflows.schemas.workflow_request" not in source
    assert "from app.application.tasks.context.task_context" not in source
    assert "from app.runtime.models.execution_context" not in source
    assert "from app.runtime.engine.runtime_engine" not in source
    assert "CRMAdapter" not in source
    assert "CRMEngine" not in source


def test_build_default_prospecting_runtime_application_service_wires_every_adapter():
    service = build_default_prospecting_runtime_application_service()

    assert isinstance(service.execution_service, ExecutionService)
    assert isinstance(service.execution_result_processor, ExecutionResultProcessor)
    assert isinstance(service.decision_adapter, DecisionAdapter)
    assert isinstance(service.rules_adapter, RulesAdapter)
    assert isinstance(service.observability_adapter, ObservabilityAdapter)
    assert isinstance(service.execution_result_processor.crm_adapter, CRMAdapter)


def test_build_default_prospecting_runtime_application_service_can_disable_adapters():
    service = build_default_prospecting_runtime_application_service(
        enable_decision=False, enable_rules=False, enable_observability=False
    )

    assert service.decision_adapter is None
    assert service.rules_adapter is None
    assert service.observability_adapter is None
    assert isinstance(service.execution_service, ExecutionService)
    assert isinstance(service.execution_result_processor, ExecutionResultProcessor)
