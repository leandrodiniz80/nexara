import inspect
from datetime import datetime, timezone

from app.crm.services.sales_report_section import SalesReportSection
from app.presentation import presentation_facade
from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_coordinator import PresentationCoordinator
from app.presentation.presentation_facade import PresentationFacade
from app.presentation.presentation_facade_factory import build_default_presentation_facade
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


def _real_coordinator() -> PresentationCoordinator:
    return PresentationCoordinator(
        ExecutiveViewService(), ExecutivePayloadService(), ResponseEnvelopeService()
    )


class _CountingCoordinator:
    def __init__(self) -> None:
        self.calls = 0
        self.received_args: tuple | None = None
        self._real = _real_coordinator()

    def present(self, dashboard, report, kpis, *, warnings=(), request_id=None):
        self.calls += 1
        self.received_args = (dashboard, report, kpis, warnings, request_id)
        return self._real.present(
            dashboard, report, kpis, warnings=warnings, request_id=request_id
        )


def test_delegacao_forwards_the_exact_arguments_to_the_coordinator():
    coordinator = _CountingCoordinator()
    facade = PresentationFacade(coordinator)
    dashboard, report, kpis = _dashboard_view(), _report_view(), _kpi_views()

    facade.present(dashboard, report, kpis, warnings=["Meta distante"], request_id="req-1")

    assert coordinator.received_args == (dashboard, report, kpis, ["Meta distante"], "req-1")


def test_coordinator_chamado_exatamente_uma_vez():
    coordinator = _CountingCoordinator()
    facade = PresentationFacade(coordinator)

    facade.present(_dashboard_view(), _report_view(), _kpi_views())

    assert coordinator.calls == 1


def test_retorno_e_response_envelope_never_a_presentation_result():
    facade = PresentationFacade(_real_coordinator())

    result = facade.present(_dashboard_view(), _report_view(), _kpi_views())

    assert isinstance(result, ResponseEnvelope)
    assert not isinstance(result, PresentationResult)
    assert result.success is True


def test_injecao_de_dependencia_uses_exactly_the_coordinator_provided():
    coordinator = _CountingCoordinator()

    facade = PresentationFacade(coordinator)

    assert facade._coordinator is coordinator


def test_build_default_presentation_facade_returns_a_usable_facade():
    facade = build_default_presentation_facade()

    assert isinstance(facade, PresentationFacade)
    result = facade.present(_dashboard_view(), _report_view(), _kpi_views())
    assert isinstance(result, ResponseEnvelope)


def test_nenhum_import_de_crm():
    source = inspect.getsource(presentation_facade)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(presentation_facade)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(presentation_facade)
    assert "Workflow" not in source


def test_nenhum_import_de_application():
    source = inspect.getsource(presentation_facade)
    assert "app.application" not in source
