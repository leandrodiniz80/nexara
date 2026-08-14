import inspect
from datetime import datetime, timezone
from typing import Any

from app.application.handlers import executive_dashboard_handler
from app.application.handlers.executive_dashboard_handler import ExecutiveDashboardHandler
from app.application.handlers.handler_registry_service import HandlerRegistryService
from app.application.handlers.handler_registry_service_factory import (
    build_default_handler_registry_service,
)
from app.application.public.public_use_case_service_factory import (
    build_default_public_use_case_service,
)
from app.contracts.public_response import PublicResponse
from app.crm.services.sales_report_section import SalesReportSection
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView

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


class _FakePublicUseCaseService:
    def __init__(self, response: Any = None) -> None:
        self.response = response if response is not None else {"ok": True}
        self.calls = 0
        self.received_args: tuple | None = None

    def execute(self, dashboard, report, kpis, *, warnings=(), request_id=None):
        self.calls += 1
        self.received_args = (dashboard, report, kpis, warnings, request_id)
        return self.response


def test_command_name_returns_executive_dashboard():
    handler = ExecutiveDashboardHandler(_FakePublicUseCaseService())

    assert handler.command_name() == "executive_dashboard"


def test_injecao_uses_exactly_the_service_provided():
    fake = _FakePublicUseCaseService()

    handler = ExecutiveDashboardHandler(fake)

    assert handler._public_use_case_service is fake


def test_delegacao_calls_execute_with_the_unpacked_payload():
    fake = _FakePublicUseCaseService(response={"score": 90})
    handler = ExecutiveDashboardHandler(fake)
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    result = handler.handle((dashboard, report, kpis))

    assert fake.calls == 1
    assert result == {"score": 90}


def test_payload_preservado_forwards_the_exact_objects():
    fake = _FakePublicUseCaseService()
    handler = ExecutiveDashboardHandler(fake)
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    handler.handle((dashboard, report, kpis))

    received_dashboard, received_report, received_kpis, _, _ = fake.received_args
    assert received_dashboard is dashboard
    assert received_report is report
    assert received_kpis is kpis


def test_handle_delegates_end_to_end_through_the_real_public_use_case_service():
    handler = ExecutiveDashboardHandler(build_default_public_use_case_service())

    result = handler.handle((_dashboard_view(), _report_view(), _kpi_views()))

    assert isinstance(result, PublicResponse)
    assert result.success is True


def test_handler_registrado_pela_factory():
    service = build_default_handler_registry_service()

    handler = service.find("executive_dashboard")

    assert isinstance(handler, ExecutiveDashboardHandler)


def test_registry_exists_true_for_the_registered_handler():
    service = HandlerRegistryService((ExecutiveDashboardHandler(_FakePublicUseCaseService()),))

    assert service.exists("executive_dashboard") is True


def test_registry_find_returns_the_registered_handler_instance():
    handler = ExecutiveDashboardHandler(_FakePublicUseCaseService())
    service = HandlerRegistryService((handler,))

    assert service.find("executive_dashboard") is handler


def test_nenhum_import_de_crm():
    source = inspect.getsource(executive_dashboard_handler)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(executive_dashboard_handler)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(executive_dashboard_handler)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(executive_dashboard_handler)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(executive_dashboard_handler)
    assert "app.contracts" not in source
