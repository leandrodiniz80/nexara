import uuid
from datetime import datetime, timezone

from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.integration.adapters.crm_adapter import CRMAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.vertical_slice import DEFAULT_WORKFLOW_NAME, VerticalSlice
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_result import ExecutionResult
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine
from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.schemas.prospecting.company import CompanyRead


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


def _prospecting_variables() -> dict:
    return {
        "strategy": "city",
        "query": {"city": "Goiânia"},
        "profile": CommercialProfile(segment="retail", company_size="small"),
        "company": _company(),
        "asset_type": "email",
    }


def _execution_result(*, success: bool = True, warnings=None, errors=None) -> ExecutionResult:
    execution = Execution(
        execution_type=ExecutionType.WORKFLOW,
        status=ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED,
    )
    return ExecutionResult(
        success=success, execution=execution, warnings=warnings or [], errors=errors or []
    )


class _FakeRuntimeEngine:
    def __init__(self, *, result: ExecutionResult | None = None, raises: Exception | None = None):
        self.result = result if result is not None else _execution_result()
        self.raises = raises
        self.calls = []

    async def execute_workflow(self, context):
        self.calls.append(context)
        if self.raises is not None:
            raise self.raises
        return self.result


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


class _FakeCRMAdapter:
    def __init__(self, *, raises: Exception | None = None):
        self.raises = raises
        self.calls = []

    def create_opportunity(self, *, company_name, opportunity_title):
        self.calls.append((company_name, opportunity_title))
        if self.raises is not None:
            raise self.raises
        return "an-opportunity"


class _FakeObservabilityAdapter:
    def __init__(self, *, raises: Exception | None = None):
        self.raises = raises
        self.calls = []

    def record(self, *, operation, execution_time, success):
        self.calls.append((operation, success))
        if self.raises is not None:
            raise self.raises


async def test_full_execution_end_to_end_with_every_real_adapter():
    """Uses the real RuntimeEngine (and, underneath it, the real WorkflowEngine
    -> TaskExecutor -> ResearchTask/QualificationTask/CopyTask chain), plus
    real CRM and Observability engines. Only Decision/Rules are left
    unregistered (no strategies/rules exist to consult) — the point of this
    test is the Runtime/Workflow/TaskExecutor/CRM/Observability path."""
    slice_ = VerticalSlice(
        runtime_engine=build_default_runtime_engine(),
        crm_adapter=CRMAdapter(build_default_crm_engine()),
        observability_adapter=ObservabilityAdapter(build_default_observability_engine()),
    )

    result = await slice_.run_prospecting(
        company_name="Agência XYZ", variables=_prospecting_variables()
    )

    assert result.data["execution"].execution.execution_type == ExecutionType.WORKFLOW
    assert result.data["opportunity"] is not None
    assert result.data["opportunity"].title == "Prospecting - Agência XYZ"
    assert result.execution_time >= 0


async def test_decision_is_optional_the_default_workflow_is_used_without_it():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(runtime_engine=runtime, decision_adapter=None)

    await slice_.run_prospecting(company_name="Agência XYZ")

    assert runtime.calls[0].workflow_request.workflow_name == DEFAULT_WORKFLOW_NAME


async def test_decision_adapter_overrides_the_default_workflow():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(
        runtime_engine=runtime, decision_adapter=_FakeDecisionAdapter(chosen="Proposal Workflow")
    )

    await slice_.run_prospecting(company_name="Agência XYZ")

    assert runtime.calls[0].workflow_request.workflow_name == "Proposal Workflow"


async def test_rules_adapter_blocks_execution_when_not_eligible():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(runtime_engine=runtime, rules_adapter=_FakeRulesAdapter(eligible=False))

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is False
    assert runtime.calls == []
    assert any("not eligible" in error for error in result.errors)


async def test_rules_adapter_allows_execution_when_eligible():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(runtime_engine=runtime, rules_adapter=_FakeRulesAdapter(eligible=True))

    await slice_.run_prospecting(company_name="Agência XYZ")

    assert len(runtime.calls) == 1


async def test_rules_are_optional_execution_proceeds_without_a_rules_adapter():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(runtime_engine=runtime, rules_adapter=None)

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert len(runtime.calls) == 1
    assert result.success is True


async def test_crm_is_optional_no_opportunity_is_created_without_it():
    slice_ = VerticalSlice(runtime_engine=_FakeRuntimeEngine(), crm_adapter=None)

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.data["opportunity"] is None


async def test_crm_adapter_is_called_when_provided():
    crm = _FakeCRMAdapter()
    slice_ = VerticalSlice(runtime_engine=_FakeRuntimeEngine(), crm_adapter=crm)

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert crm.calls == [("Agência XYZ", "Prospecting - Agência XYZ")]
    assert result.data["opportunity"] == "an-opportunity"


async def test_observability_is_optional_nothing_raises_without_it():
    slice_ = VerticalSlice(runtime_engine=_FakeRuntimeEngine(), observability_adapter=None)

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is True


async def test_observability_adapter_is_called_when_provided():
    observability = _FakeObservabilityAdapter()
    slice_ = VerticalSlice(runtime_engine=_FakeRuntimeEngine(), observability_adapter=observability)

    await slice_.run_prospecting(company_name="Agência XYZ")

    assert observability.calls == [("run_prospecting", True)]


async def test_decision_adapter_failure_is_downgraded_to_a_warning():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(
        runtime_engine=runtime, decision_adapter=_FakeDecisionAdapter(raises=RuntimeError("boom"))
    )

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is True
    assert runtime.calls[0].workflow_request.workflow_name == DEFAULT_WORKFLOW_NAME
    assert any("DecisionAdapter" in warning for warning in result.warnings)


async def test_rules_adapter_failure_is_downgraded_to_a_warning_and_execution_proceeds():
    runtime = _FakeRuntimeEngine()
    slice_ = VerticalSlice(
        runtime_engine=runtime, rules_adapter=_FakeRulesAdapter(raises=RuntimeError("boom"))
    )

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is True
    assert len(runtime.calls) == 1
    assert any("RulesAdapter" in warning for warning in result.warnings)


async def test_crm_adapter_failure_is_downgraded_to_a_warning():
    slice_ = VerticalSlice(
        runtime_engine=_FakeRuntimeEngine(),
        crm_adapter=_FakeCRMAdapter(raises=RuntimeError("boom")),
    )

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is True
    assert result.data["opportunity"] is None
    assert any("CRMAdapter" in warning for warning in result.warnings)


async def test_observability_adapter_failure_is_downgraded_to_a_warning():
    slice_ = VerticalSlice(
        runtime_engine=_FakeRuntimeEngine(),
        observability_adapter=_FakeObservabilityAdapter(raises=RuntimeError("boom")),
    )

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is True
    assert any("ObservabilityAdapter" in warning for warning in result.warnings)


async def test_runtime_failure_marks_the_whole_result_unsuccessful():
    runtime = _FakeRuntimeEngine(raises=RuntimeError("no such workflow"))
    slice_ = VerticalSlice(runtime_engine=runtime)

    result = await slice_.run_prospecting(company_name="Agência XYZ")

    assert result.success is False
    assert any("Runtime execution failed" in error for error in result.errors)
    assert result.data is None
