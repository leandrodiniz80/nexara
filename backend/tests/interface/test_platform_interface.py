import inspect
from datetime import datetime, timezone

from app.contracts.public_response import PublicResponse
from app.contracts.response_mapper import ResponseMapper
from app.crm.services.sales_report_section import SalesReportSection
from app.interface import platform_interface
from app.interface.platform_interface import PlatformInterface
from app.interface.platform_interface_factory import build_default_platform_interface
from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.presentation_facade import PresentationFacade
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


def _real_facade() -> PresentationFacade:
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )
    return PresentationFacade(coordinator)


class _CountingFacade:
    def __init__(self) -> None:
        self.calls = 0
        self._real = _real_facade()

    def present(self, dashboard, report, kpis, *, warnings=(), request_id=None):
        self.calls += 1
        return self._real.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )


class _CountingMapper:
    def __init__(self) -> None:
        self.calls = 0
        self.received_envelope: ResponseEnvelope | None = None
        self._real = ResponseMapper()

    def to_public_response(self, response):
        self.calls += 1
        self.received_envelope = response
        return self._real.to_public_response(response)


def test_fluxo_completo_returns_a_populated_public_response():
    interface = PlatformInterface(_real_facade(), ResponseMapper())

    response = interface.present(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(response, PublicResponse)
    assert response.success is True
    assert response.payload is not None


def test_delegacao_forwards_the_facades_envelope_into_the_mapper():
    facade = _CountingFacade()
    mapper = _CountingMapper()
    interface = PlatformInterface(facade, mapper)

    interface.present(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(mapper.received_envelope, ResponseEnvelope)


def test_presentation_facade_chamado_exatamente_uma_vez():
    facade = _CountingFacade()
    mapper = _CountingMapper()
    interface = PlatformInterface(facade, mapper)

    interface.present(_dashboard_view(), _report_view(), _kpi_views())

    assert facade.calls == 1


def test_response_mapper_chamado_exatamente_uma_vez():
    facade = _CountingFacade()
    mapper = _CountingMapper()
    interface = PlatformInterface(facade, mapper)

    interface.present(_dashboard_view(), _report_view(), _kpi_views())

    assert mapper.calls == 1


def test_retorno_e_public_response_never_a_response_envelope():
    interface = PlatformInterface(_real_facade(), ResponseMapper())

    result = interface.present(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(result, PublicResponse)
    assert not isinstance(result, ResponseEnvelope)


def test_injecao_uses_exactly_the_collaborators_provided():
    facade = _CountingFacade()
    mapper = _CountingMapper()

    interface = PlatformInterface(facade, mapper)

    assert interface._presentation_facade is facade
    assert interface._response_mapper is mapper


def test_build_default_platform_interface_returns_a_usable_interface():
    interface = build_default_platform_interface()

    assert isinstance(interface, PlatformInterface)
    response = interface.present(_dashboard_view(), _report_view(), _kpi_views())
    assert isinstance(response, PublicResponse)


def test_nenhum_import_de_crm():
    source = inspect.getsource(platform_interface)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(platform_interface)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(platform_interface)
    assert "Workflow" not in source


def test_nenhum_import_de_application():
    source = inspect.getsource(platform_interface)
    assert "app.application" not in source
