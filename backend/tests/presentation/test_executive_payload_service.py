import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services.sales_report_section import SalesReportSection
from app.presentation import executive_payload_service
from app.presentation.executive_payload import ExecutivePayload
from app.presentation.executive_payload_service import ExecutivePayloadService
from app.presentation.executive_payload_service_factory import (
    build_default_executive_payload_service,
)
from app.presentation.executive_view import ExecutiveView
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


def _view() -> ExecutiveView:
    return ExecutiveView(
        dashboard=_dashboard_view(),
        report=_report_view(),
        kpis=_kpi_views(),
        generated_at=_T0,
    )


def test_payload_preservado_copies_every_field_without_recalculation():
    view = _view()
    service = ExecutivePayloadService()

    payload = service.build(view)

    assert isinstance(payload, ExecutivePayload)
    assert payload.title == view.report.title
    assert payload.generated_at == view.generated_at


def test_dashboard_preservado_keeps_the_exact_instance():
    view = _view()
    service = ExecutivePayloadService()

    payload = service.build(view)

    assert payload.dashboard is view.dashboard


def test_report_preservado_keeps_the_exact_instance():
    view = _view()
    service = ExecutivePayloadService()

    payload = service.build(view)

    assert payload.report is view.report
    assert payload.title == "Executive Sales Report"


def test_kpis_preservados_in_the_same_order_and_content():
    view = _view()
    service = ExecutivePayloadService()

    payload = service.build(view)

    assert payload.kpis == view.kpis
    assert payload.kpis[0] is view.kpis[0]
    assert payload.kpis[1] is view.kpis[1]


def test_metadata_construida_corretamente():
    view = _view()
    service = ExecutivePayloadService()

    payload = service.build(view)

    assert payload.metadata == {
        "application": "Elevel Prospect AI",
        "version": "1.0.0",
        "generated_at": view.generated_at,
    }


def test_imutabilidade_rejects_attribute_assignment():
    service = ExecutivePayloadService()

    payload = service.build(_view())

    with pytest.raises(ValidationError):
        payload.title = "Alterado"

    with pytest.raises(ValidationError):
        payload.metadata = {}


def test_build_default_executive_payload_service_returns_a_usable_service():
    service = build_default_executive_payload_service()

    assert isinstance(service, ExecutivePayloadService)
    payload = service.build(_view())
    assert isinstance(payload, ExecutivePayload)


def test_nenhum_import_de_crm():
    source = inspect.getsource(executive_payload_service)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(executive_payload_service)
    assert "Runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(executive_payload_service)
    assert "Workflow" not in source
