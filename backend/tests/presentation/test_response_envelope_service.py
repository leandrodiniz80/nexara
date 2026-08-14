import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services.sales_report_section import SalesReportSection
from app.presentation import response_envelope_service
from app.presentation.executive_payload import ExecutivePayload
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.response_envelope import ResponseEnvelope
from app.presentation.response_envelope_service import ResponseEnvelopeService
from app.presentation.response_envelope_service_factory import (
    build_default_response_envelope_service,
)

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


def test_success_builds_a_successful_envelope_with_no_errors():
    payload = _payload()
    service = ResponseEnvelopeService()

    envelope = service.success(payload)

    assert envelope.success is True
    assert envelope.payload is payload
    assert envelope.errors == ()
    assert envelope.warnings == ()


def test_success_accepts_optional_warnings():
    payload = _payload()
    service = ResponseEnvelopeService()

    envelope = service.success(payload, warnings=["Meta distante"])

    assert envelope.success is True
    assert envelope.warnings == ("Meta distante",)
    assert envelope.errors == ()


def test_warning_builds_a_successful_envelope_with_warnings_and_no_errors():
    payload = _payload()
    service = ResponseEnvelopeService()

    envelope = service.warning(payload, ["Cadência muito lenta", "Meta distante"])

    assert envelope.success is True
    assert envelope.payload is payload
    assert envelope.warnings == ("Cadência muito lenta", "Meta distante")
    assert envelope.errors == ()


def test_failure_builds_an_unsuccessful_envelope_with_no_payload():
    service = ResponseEnvelopeService()

    envelope = service.failure(["Oportunidade não encontrada."], now=_T0)

    assert envelope.success is False
    assert envelope.payload is None
    assert envelope.errors == ("Oportunidade não encontrada.",)
    assert envelope.warnings == ()


def test_failure_accepts_optional_warnings_alongside_errors():
    service = ResponseEnvelopeService()

    envelope = service.failure(
        ["Falha ao processar."], warnings=["Dados parcialmente carregados."], now=_T0
    )

    assert envelope.success is False
    assert envelope.errors == ("Falha ao processar.",)
    assert envelope.warnings == ("Dados parcialmente carregados.",)


def test_payload_preservado_keeps_the_exact_instance_and_is_never_altered():
    payload = _payload()
    service = ResponseEnvelopeService()

    envelope = service.success(payload)

    assert envelope.payload is payload
    assert envelope.payload.title == "Executive Sales Report"
    assert envelope.payload.kpis == payload.kpis


def test_metadata_criada_contains_exactly_the_expected_keys():
    payload = _payload()
    service = ResponseEnvelopeService()

    envelope = service.success(payload)

    assert envelope.metadata == {
        "generated_at": payload.generated_at,
        "version": "1.0.0",
        "application": "Elevel Prospect AI",
    }


def test_metadata_includes_request_id_when_provided():
    payload = _payload()
    service = ResponseEnvelopeService()

    envelope = service.success(payload, request_id="req-123")

    assert envelope.metadata["request_id"] == "req-123"
    assert set(envelope.metadata.keys()) == {
        "generated_at",
        "version",
        "application",
        "request_id",
    }


def test_imutabilidade_rejects_attribute_assignment():
    service = ResponseEnvelopeService()

    envelope = service.success(_payload())

    with pytest.raises(ValidationError):
        envelope.success = False

    with pytest.raises(ValidationError):
        envelope.metadata = {}


def test_build_default_response_envelope_service_returns_a_usable_service():
    service = build_default_response_envelope_service()

    assert isinstance(service, ResponseEnvelopeService)
    envelope = service.success(_payload())
    assert isinstance(envelope, ResponseEnvelope)


def test_nenhum_import_de_crm():
    source = inspect.getsource(response_envelope_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(response_envelope_service)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(response_envelope_service)
    assert "Workflow" not in source


def test_nenhum_import_de_application():
    source = inspect.getsource(response_envelope_service)
    assert "app.application" not in source
