import inspect
from datetime import datetime, timezone

from app.contracts import response_mapper
from app.contracts.public_error import PublicError
from app.contracts.public_response import PublicResponse
from app.contracts.public_warning import PublicWarning
from app.contracts.response_mapper import ResponseMapper
from app.contracts.response_mapper_factory import build_default_response_mapper
from app.crm.services.sales_report_section import SalesReportSection
from app.presentation.executive_payload import ExecutivePayload
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.response_envelope_service import ResponseEnvelopeService

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _payload() -> ExecutivePayload:
    dashboard = DashboardView(
        title="Sales Dashboard",
        overall_health="good",
        overall_score=60.0,
        cards=[{"label": "Expected Revenue", "value": 5000.0}],
        highlights=["Alta confiança na previsão"],
        warnings=["Meta distante"],
        generated_at=_T0,
    )
    report = ReportView(
        title="Executive Sales Report",
        subtitle=_T0.isoformat(),
        sections=[SalesReportSection(title="Resumo Executivo", items={"overall_score": 60.0})],
        footer="Generated automatically by Elevel Prospect AI",
    )
    kpis = [KPIView(name="Forecast Confidence", value=60.0, unit="%", status="ATTENTION")]
    return ExecutivePayload(
        title="Executive Sales Report",
        generated_at=_T0,
        dashboard=dashboard,
        report=report,
        kpis=kpis,
        metadata={"application": "Elevel Prospect AI", "version": "1.0.0", "generated_at": _T0},
    )


def test_response_completa_maps_every_field():
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.warning(
        _payload(), ["Cadência muito lenta."], request_id="req-123"
    )
    mapper = ResponseMapper()

    public_response = mapper.to_public_response(envelope)

    assert isinstance(public_response, PublicResponse)
    assert public_response.success is True
    assert public_response.payload is envelope.payload
    assert public_response.metadata.application == "Elevel Prospect AI"
    assert public_response.metadata.version == "1.0.0"
    assert public_response.metadata.generated_at == envelope.metadata["generated_at"]
    assert public_response.metadata.request_id == "req-123"
    expected_warning = PublicWarning(code="WARNING", message="Cadência muito lenta.")
    assert public_response.warnings == (expected_warning,)
    assert public_response.errors == ()


def test_response_sem_payload_maps_to_a_none_payload():
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.failure(["Oportunidade não encontrada."], now=_T0)
    mapper = ResponseMapper()

    public_response = mapper.to_public_response(envelope)

    assert public_response.success is False
    assert public_response.payload is None
    assert public_response.errors == (
        PublicError(code="ERROR", message="Oportunidade não encontrada."),
    )


def test_response_sem_warnings_maps_to_an_empty_tuple():
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.success(_payload())
    mapper = ResponseMapper()

    public_response = mapper.to_public_response(envelope)

    assert public_response.warnings == ()


def test_response_sem_errors_maps_to_an_empty_tuple():
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.success(_payload())
    mapper = ResponseMapper()

    public_response = mapper.to_public_response(envelope)

    assert public_response.errors == ()


def test_payload_preservado_is_never_converted():
    payload = _payload()
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.success(payload)
    mapper = ResponseMapper()

    public_response = mapper.to_public_response(envelope)

    assert public_response.payload is payload


def test_metadata_preservada_copies_every_field_exactly():
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.success(_payload(), request_id="req-456")
    mapper = ResponseMapper()

    public_response = mapper.to_public_response(envelope)

    assert public_response.metadata.application == envelope.metadata["application"]
    assert public_response.metadata.version == envelope.metadata["version"]
    assert public_response.metadata.generated_at == envelope.metadata["generated_at"]
    assert public_response.metadata.request_id == envelope.metadata["request_id"]


def test_build_default_response_mapper_returns_a_usable_mapper():
    mapper = build_default_response_mapper()
    envelope_service = ResponseEnvelopeService()
    envelope = envelope_service.success(_payload())

    assert isinstance(mapper, ResponseMapper)
    public_response = mapper.to_public_response(envelope)
    assert isinstance(public_response, PublicResponse)


def test_nenhum_import_de_crm():
    source = inspect.getsource(response_mapper)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(response_mapper)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(response_mapper)
    assert "Workflow" not in source
