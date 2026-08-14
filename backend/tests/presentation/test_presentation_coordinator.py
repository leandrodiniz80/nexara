import inspect
from datetime import datetime, timezone

from app.crm.services.sales_report_section import SalesReportSection
from app.presentation import presentation_coordinator
from app.presentation.executive_payload import ExecutivePayload
from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_view import ExecutiveView
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.presentation_coordinator_factory import (
    build_default_presentation_coordinator,
)
from app.presentation.presentation_result import PresentationResult
from app.presentation.response_envelope import ResponseEnvelope
from app.presentation.response_envelope_service import ResponseEnvelopeService

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _dashboard_view() -> DashboardView:
    return DashboardView(
        title="Sales Dashboard",
        overall_health="good",
        overall_score=60.0,
        cards=[{"label": "Expected Revenue", "value": 5000.0}],
        highlights=["Alta confiança na previsão"],
        warnings=["Meta distante"],
        generated_at=_T0,
    )


def _report_view() -> ReportView:
    return ReportView(
        title="Executive Sales Report",
        subtitle=_T0.isoformat(),
        sections=[SalesReportSection(title="Resumo Executivo", items={"overall_score": 60.0})],
        footer="Generated automatically by Elevel Prospect AI",
    )


def _kpi_views() -> list[KPIView]:
    return [KPIView(name="Forecast Confidence", value=60.0, unit="%", status="ATTENTION")]


class _CountingExecutiveViewService:
    def __init__(self) -> None:
        self.calls = 0
        self._real = ExecutiveViewService()

    def compose(self, dashboard, report, kpis, *, now=None):
        self.calls += 1
        return self._real.compose(dashboard, report, kpis, now=now)


class _CountingExecutivePayloadService:
    def __init__(self) -> None:
        self.calls = 0
        self._real = ExecutivePayloadService()

    def build(self, view):
        self.calls += 1
        return self._real.build(view)


class _CountingResponseEnvelopeService:
    def __init__(self) -> None:
        self.calls = 0
        self._real = ResponseEnvelopeService()

    def success(self, payload, *, warnings=(), request_id=None):
        self.calls += 1
        return self._real.success(payload, warnings=warnings, request_id=request_id)

    def warning(self, payload, warnings, *, request_id=None):
        self.calls += 1
        return self._real.warning(payload, warnings, request_id=request_id)

    def failure(self, errors, *, warnings=(), request_id=None, now=None):
        self.calls += 1
        return self._real.failure(errors, warnings=warnings, request_id=request_id, now=now)


def test_fluxo_completo_produces_a_fully_populated_presentation_result():
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )

    result = coordinator.present(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(result, PresentationResult)
    assert isinstance(result.view, ExecutiveView)
    assert isinstance(result.payload, ExecutivePayload)
    assert isinstance(result.response, ResponseEnvelope)
    assert result.response.success is True


def test_todos_os_servicos_sao_chamados_exatamente_uma_vez():
    view_service = _CountingExecutiveViewService()
    payload_service = _CountingExecutivePayloadService()
    envelope_service = _CountingResponseEnvelopeService()
    coordinator = PresentationCoordinator(view_service, payload_service, envelope_service)

    coordinator.present(_dashboard_view(), _report_view(), _kpi_views())

    assert view_service.calls == 1
    assert payload_service.calls == 1
    assert envelope_service.calls == 1


def test_payload_preservado_is_the_exact_instance_carried_into_the_response():
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )

    result = coordinator.present(_dashboard_view(), _report_view(), _kpi_views())

    assert result.response.payload is result.payload


def test_response_preservada_wraps_the_exact_payload_with_no_errors():
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )

    result = coordinator.present(_dashboard_view(), _report_view(), _kpi_views())

    assert result.response.errors == ()
    assert result.response.payload is not None


def test_presentation_result_preservado_links_view_payload_and_response_consistently():
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    result = coordinator.present(dashboard, report, kpis)

    assert result.view.dashboard is dashboard
    assert result.view.report is report
    assert result.payload.dashboard is dashboard
    assert result.payload.report is report


def test_injecao_de_dependencias_uses_exactly_the_services_provided():
    view_service = _CountingExecutiveViewService()
    payload_service = _CountingExecutivePayloadService()
    envelope_service = _CountingResponseEnvelopeService()

    coordinator = PresentationCoordinator(view_service, payload_service, envelope_service)

    assert coordinator._executive_view_service is view_service
    assert coordinator._executive_payload_service is payload_service
    assert coordinator._response_envelope_service is envelope_service


def test_build_default_presentation_coordinator_returns_a_usable_coordinator():
    coordinator = build_default_presentation_coordinator()

    assert isinstance(coordinator, PresentationCoordinator)
    result = coordinator.present(_dashboard_view(), _report_view(), _kpi_views())
    assert isinstance(result, PresentationResult)


def test_nenhum_import_de_crm():
    source = inspect.getsource(presentation_coordinator)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(presentation_coordinator)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(presentation_coordinator)
    assert "Workflow" not in source


def test_nenhum_import_de_application():
    source = inspect.getsource(presentation_coordinator)
    assert "app.application" not in source
