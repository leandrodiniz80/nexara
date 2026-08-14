import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services.sales_report_section import SalesReportSection
from app.presentation import executive_view_service
from app.presentation.executive_view import ExecutiveView
from app.presentation.executive_view_service import ExecutiveViewService
from app.presentation.executive_view_service_factory import build_default_executive_view_service
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
    return [
        KPIView(name="Forecast Confidence", value=60.0, unit="%", status="ATTENTION"),
        KPIView(name="Trend Direction", value="stable", unit="texto", status="INFO"),
    ]


def test_dashboard_preservado_keeps_the_exact_instance():
    dashboard = _dashboard_view()
    service = ExecutiveViewService()

    view = service.compose(dashboard, _report_view(), _kpi_views(), now=_T0)

    assert view.dashboard is dashboard


def test_report_preservado_keeps_the_exact_instance():
    report = _report_view()
    service = ExecutiveViewService()

    view = service.compose(_dashboard_view(), report, _kpi_views(), now=_T0)

    assert view.report is report


def test_kpis_preservados_in_the_same_order_and_content():
    kpis = _kpi_views()
    service = ExecutiveViewService()

    view = service.compose(_dashboard_view(), _report_view(), kpis, now=_T0)

    assert view.kpis == kpis
    assert view.kpis[0] is kpis[0]
    assert view.kpis[1] is kpis[1]


def test_imutabilidade_rejects_attribute_assignment():
    service = ExecutiveViewService()

    view = service.compose(_dashboard_view(), _report_view(), _kpi_views(), now=_T0)

    with pytest.raises(ValidationError):
        view.generated_at = _T0

    with pytest.raises(ValidationError):
        view.kpis = []


def test_build_default_executive_view_service_returns_a_usable_service():
    service = build_default_executive_view_service()

    assert isinstance(service, ExecutiveViewService)
    view = service.compose(_dashboard_view(), _report_view(), _kpi_views(), now=_T0)
    assert isinstance(view, ExecutiveView)


def test_nenhum_import_de_crm():
    source = inspect.getsource(executive_view_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(executive_view_service)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(executive_view_service)
    assert "Workflow" not in source
