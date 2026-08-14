import inspect
from datetime import datetime, timezone

from app.application.interface import application_interface_service
from app.application.interface.application_interface_service import ApplicationInterfaceService
from app.application.interface.application_interface_service_factory import (
    build_default_application_interface_service,
)
from app.contracts.public_response import PublicResponse
from app.contracts.response_mapper import ResponseMapper
from app.crm.services.sales_report_section import SalesReportSection
from app.interface.platform_interface import PlatformInterface
from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.presentation_facade import PresentationFacade
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


def _real_platform_interface() -> PlatformInterface:
    coordinator = PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )
    facade = PresentationFacade(coordinator)
    return PlatformInterface(facade, ResponseMapper())


class _CountingPlatformInterface:
    def __init__(self) -> None:
        self.calls = 0
        self.received_args: tuple | None = None
        self._real = _real_platform_interface()

    def present(self, dashboard, report, kpis, *, warnings=(), request_id=None):
        self.calls += 1
        self.received_args = (dashboard, report, kpis, warnings, request_id)
        return self._real.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )


def test_delegacao_forwards_the_exact_arguments():
    platform_interface = _CountingPlatformInterface()
    service = ApplicationInterfaceService(platform_interface)
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    service.present(dashboard, report, kpis, warnings=["Meta distante"], request_id="req-1")

    assert platform_interface.received_args == (
        dashboard,
        report,
        kpis,
        ["Meta distante"],
        "req-1",
    )


def test_platform_interface_chamado_exatamente_uma_vez():
    platform_interface = _CountingPlatformInterface()
    service = ApplicationInterfaceService(platform_interface)

    service.present(_dashboard_view(), _report_view(), _kpi_views())

    assert platform_interface.calls == 1


def test_retorno_e_public_response():
    service = ApplicationInterfaceService(_real_platform_interface())

    result = service.present(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(result, PublicResponse)
    assert result.success is True


def test_injecao_uses_exactly_the_platform_interface_provided():
    platform_interface = _CountingPlatformInterface()

    service = ApplicationInterfaceService(platform_interface)

    assert service._platform_interface is platform_interface


def test_build_default_application_interface_service_returns_a_usable_service():
    service = build_default_application_interface_service()

    assert isinstance(service, ApplicationInterfaceService)
    result = service.present(_dashboard_view(), _report_view(), _kpi_views())
    assert isinstance(result, PublicResponse)


def test_nenhum_import_de_crm():
    source = inspect.getsource(application_interface_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(application_interface_service)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(application_interface_service)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(application_interface_service)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(application_interface_service)
    assert "app.contracts" not in source
