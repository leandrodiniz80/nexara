import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services import sales_report_builder_service
from app.crm.services.executive_sales_dashboard import ExecutiveHealth, ExecutiveSalesDashboard
from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_report import SalesReport
from app.crm.services.sales_report_builder import SalesReportBuilder
from app.crm.services.sales_report_builder_service import SalesReportBuilderService
from app.crm.services.sales_report_builder_service_factory import (
    build_default_sales_report_builder_service,
)
from app.crm.services.sales_report_section import SalesReportSection
from app.crm.services.sales_target import SalesTarget
from app.crm.services.sales_target_progress import SalesTargetProgress
from app.crm.services.sales_trend import SalesTrend, SalesTrendDirection

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 3, 11, 9, 30, tzinfo=timezone.utc)


def _dashboard() -> ExecutiveSalesDashboard:
    forecast = SalesForecast(
        total_pipeline_value=10000.0,
        expected_revenue=5000.0,
        average_probability=0.5,
        forecast_confidence=60.0,
        won_value=0.0,
        lost_value=0.0,
        open_value=10000.0,
        forecast_items=[],
        generated_at=_T0,
    )
    target = SalesTarget(
        name="Meta Q1",
        period="2026-Q1",
        target_revenue=10000.0,
        target_opportunities=10,
        target_conversion_rate=0.7,
        created_at=_T0,
    )
    target_progress = SalesTargetProgress(
        target=target,
        current_revenue=5000.0,
        current_opportunities=6,
        current_conversion_rate=0.42,
        revenue_progress=0.5,
        opportunity_progress=0.5,
        conversion_progress=0.5,
        overall_progress=0.5,
        is_completed=False,
        generated_at=_T0,
    )
    pipeline_summary = SalesPipelineSummary(
        total_opportunities=4,
        healthy=3,
        attention=1,
        critical=0,
        average_completion_rate=60.0,
        average_duration=None,
        total_pauses=0,
        total_rollbacks=0,
        total_finished=0,
        overall_health=SalesCoachingHealth.HEALTHY,
        insights=[],
        generated_at=_T0,
    )
    trend = SalesTrend(
        trend_direction=SalesTrendDirection.STABLE,
        revenue_delta=0.0,
        completion_delta=0.0,
        progress_delta=0.0,
        health_delta=0,
        is_improving=True,
        generated_at=_T0,
    )
    return ExecutiveSalesDashboard(
        forecast=forecast,
        target_progress=target_progress,
        pipeline_summary=pipeline_summary,
        trend=trend,
        generated_at=_T0,
        overall_health=ExecutiveHealth.GOOD,
        overall_score=60.0,
        highlights=[],
        warnings=[],
    )


def _report(*, sections: list[SalesReportSection] | None = None) -> SalesReport:
    return SalesReport(
        dashboard=_dashboard(),
        kpis=SalesKPICatalog(kpis=[], overall_score=60.0, generated_at=_T0),
        sections=sections if sections is not None else [
            SalesReportSection(title="Resumo Executivo", items={"overall_score": 60.0}),
            SalesReportSection(title="Financeiro", items={"expected_revenue": 5000.0}),
        ],
        generated_at=_T1,
    )


def test_builder_vazio_preserves_an_empty_section_list():
    report = _report(sections=[])
    service = SalesReportBuilderService()

    builder = service.build(report, now=_T1)

    assert builder.sections == []


def test_title_correto():
    service = SalesReportBuilderService()

    builder = service.build(_report(), now=_T1)

    assert builder.title == "Executive Sales Report"


def test_subtitle_correto_is_the_reports_generated_at_as_iso8601():
    report = _report()
    service = SalesReportBuilderService()

    builder = service.build(report, now=_T1)

    assert builder.subtitle == _T1.isoformat()
    assert builder.subtitle == report.generated_at.isoformat()


def test_sections_preservadas_exactly_as_given():
    report = _report()
    service = SalesReportBuilderService()

    builder = service.build(report, now=_T1)

    assert builder.sections == report.sections
    assert builder.sections[0] is report.sections[0]
    assert builder.sections[1] is report.sections[1]


def test_footer_correto():
    service = SalesReportBuilderService()

    builder = service.build(_report(), now=_T1)

    assert builder.footer == "Generated automatically by Elevel Prospect AI"


def test_imutabilidade_rejects_attribute_assignment():
    service = SalesReportBuilderService()

    builder = service.build(_report(), now=_T1)

    with pytest.raises(ValidationError):
        builder.title = "Alterado"

    with pytest.raises(ValidationError):
        builder.sections[0].title = "Alterado"


def test_build_default_sales_report_builder_service_returns_a_usable_service():
    service = build_default_sales_report_builder_service()

    assert isinstance(service, SalesReportBuilderService)
    builder = service.build(_report(), now=_T1)
    assert isinstance(builder, SalesReportBuilder)
    assert builder.title == "Executive Sales Report"


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_report_builder_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_report_builder_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_report_builder_service)
    assert "CRMEngine" not in source
