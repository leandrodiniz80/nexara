import uuid
from datetime import datetime, timezone

from app.application.execution.execution_result_processor import ExecutionResultProcessor
from app.application.execution.execution_result_processor_factory import (
    build_default_execution_result_processor,
)
from app.bootstrap.bootstrap import Bootstrap
from app.config.settings import PlatformSettings
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.integration.adapters.crm_adapter import CRMAdapter
from app.models.prospecting.enums import ProspectStage, ProspectStatus, ProspectTemperature
from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.models.execution_result import ExecutionResult
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


def _execution_result(*, success: bool = True, warnings=None, errors=None) -> ExecutionResult:
    execution = Execution(
        execution_type=ExecutionType.WORKFLOW,
        status=ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED,
    )
    return ExecutionResult(
        success=success, execution=execution, warnings=warnings or [], errors=errors or []
    )


class _FakeCRMAdapter:
    def __init__(self, *, raises: Exception | None = None):
        self.raises = raises
        self.calls = []

    def create_opportunity(self, *, company_name, opportunity_title):
        self.calls.append((company_name, opportunity_title))
        if self.raises is not None:
            raise self.raises
        return "an-opportunity"


def test_full_execution_with_opportunity_created():
    processor = ExecutionResultProcessor(_FakeCRMAdapter())
    execution_result = _execution_result()

    result = processor.process(execution_result, company=_company(), prospect=_prospect())

    assert result.execution_result is execution_result
    assert result.crm_opportunity == "an-opportunity"
    assert result.errors == []


def test_full_execution_with_a_real_crm_adapter_creates_a_real_opportunity():
    processor = ExecutionResultProcessor(CRMAdapter(build_default_crm_engine()))
    execution_result = _execution_result()

    result = processor.process(execution_result, company=_company(), prospect=_prospect())

    assert result.crm_opportunity is not None
    assert result.crm_opportunity.title == "Prospecting - Agência XYZ"


def test_execution_without_a_prospect_never_registers_an_opportunity():
    adapter = _FakeCRMAdapter()
    processor = ExecutionResultProcessor(adapter)
    execution_result = _execution_result()

    result = processor.process(execution_result, company=_company(), prospect=None)

    assert result.crm_opportunity is None
    assert adapter.calls == []


def test_execution_without_a_company_never_registers_an_opportunity():
    adapter = _FakeCRMAdapter()
    processor = ExecutionResultProcessor(adapter)
    execution_result = _execution_result()

    result = processor.process(execution_result, company=None, prospect=_prospect())

    assert result.crm_opportunity is None
    assert adapter.calls == []


def test_crm_unavailable_because_no_adapter_was_given_is_silently_skipped():
    processor = ExecutionResultProcessor(crm_adapter=None)
    execution_result = _execution_result()

    result = processor.process(execution_result, company=_company(), prospect=_prospect())

    assert result.crm_opportunity is None
    assert result.warnings == []


def test_crm_adapter_failure_is_downgraded_to_a_warning_execution_stays_success():
    processor = ExecutionResultProcessor(_FakeCRMAdapter(raises=ConnectionError("crm down")))
    execution_result = _execution_result(success=True)

    result = processor.process(execution_result, company=_company(), prospect=_prospect())

    assert result.crm_opportunity is None
    assert any("CRMAdapter" in warning for warning in result.warnings)
    assert result.execution_result.success is True


def test_empty_execution_result_is_processed_without_error():
    processor = ExecutionResultProcessor(_FakeCRMAdapter())
    execution_result = ExecutionResult(
        success=True,
        execution=Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.SUCCESS),
    )

    result = processor.process(execution_result)

    assert result.crm_opportunity is None
    assert result.warnings == []
    assert result.errors == []


def test_failed_workflow_execution_still_processes_without_raising():
    processor = ExecutionResultProcessor(_FakeCRMAdapter())
    execution_result = _execution_result(success=False, errors=["qualification failed"])

    result = processor.process(execution_result, company=_company(), prospect=None)

    assert result.execution_result.success is False
    assert result.errors == ["qualification failed"]
    assert result.crm_opportunity is None


def test_warnings_from_the_execution_result_are_propagated():
    processor = ExecutionResultProcessor(crm_adapter=None)
    execution_result = _execution_result(warnings=["step 2 continued after failure"])

    result = processor.process(execution_result)

    assert result.warnings == ["step 2 continued after failure"]


def test_build_default_execution_result_processor_wires_a_real_crm_adapter_by_default():
    processor = build_default_execution_result_processor()

    assert isinstance(processor.crm_adapter, CRMAdapter)


def test_build_default_execution_result_processor_has_no_adapter_when_crm_is_disabled():
    bootstrap = Bootstrap(PlatformSettings(enabled_modules=["runtime"]))

    processor = build_default_execution_result_processor(bootstrap=bootstrap)

    assert processor.crm_adapter is None


def test_execution_result_processor_never_calls_runtime_or_workflow():
    """Sweep-level guarantee: this file must not import RuntimeEngine,
    WorkflowEngine, or WorkflowRequest at all — it only ever receives an
    already-finished ExecutionResult."""
    import app.application.execution.execution_result_processor as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    assert "RuntimeEngine" not in source
    assert "WorkflowEngine" not in source
    assert "WorkflowRequest" not in source
    assert "TaskExecutor" not in source
