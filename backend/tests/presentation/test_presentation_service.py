import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services.executive_sales_dashboard import ExecutiveHealth, ExecutiveSalesDashboard
from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_kpi import SalesKPI
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_report_builder import SalesReportBuilder
from app.crm.services.sales_report_section import SalesReportSection
from app.crm.services.sales_target import SalesTarget
from app.crm.services.sales_target_progress import SalesTargetProgress
from app.crm.services.sales_trend import SalesTrend, SalesTrendDirection
from app.presentation import presentation_service
from app.presentation.models.dashboard_view import DashboardView
from app.presentation.models.kpi_view import KPIView
from app.presentation.models.report_view import ReportView
from app.presentation.presentation_service import PresentationService
from app.presentation.presentation_service_factory import build_default_presentation_service

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _dashboard(
    *,
    forecast_confidence: float = 60.0,
    expected_revenue: float = 5000.0,
    overall_progress: float = 0.6,
    average_completion_rate: float = 60.0,
    overall_health: ExecutiveHealth = ExecutiveHealth.GOOD,
    overall_score: float = 60.0,
    trend_direction: SalesTrendDirection = SalesTrendDirection.STABLE,
    pipeline_health: SalesCoachingHealth = SalesCoachingHealth.HEALTHY,
    highlights: list[str] | None = None,
    warnings: list[str] | None = None,
) -> ExecutiveSalesDashboard:
    forecast = SalesForecast(
        total_pipeline_value=10000.0,
        expected_revenue=expected_revenue,
        average_probability=0.5,
        forecast_confidence=forecast_confidence,
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
        current_revenue=expected_revenue,
        current_opportunities=6,
        current_conversion_rate=0.42,
        revenue_progress=overall_progress,
        opportunity_progress=overall_progress,
        conversion_progress=overall_progress,
        overall_progress=overall_progress,
        is_completed=overall_progress >= 1.0,
        generated_at=_T0,
    )
    pipeline_summary = SalesPipelineSummary(
        total_opportunities=4,
        healthy=3,
        attention=1,
        critical=0,
        average_completion_rate=average_completion_rate,
        average_duration=None,
        total_pauses=0,
        total_rollbacks=0,
        total_finished=0,
        overall_health=pipeline_health,
        insights=[],
        generated_at=_T0,
    )
    trend = SalesTrend(
        trend_direction=trend_direction,
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
        overall_health=overall_health,
        overall_score=overall_score,
        highlights=highlights or [],
        warnings=warnings or [],
    )


def test_dashboard_vazio_still_produces_six_zeroed_cards():
    dashboard = _dashboard(
        forecast_confidence=0.0,
        expected_revenue=0.0,
        overall_progress=0.0,
        average_completion_rate=0.0,
        overall_score=0.0,
    )
    service = PresentationService()

    view = service.to_dashboard_view(dashboard)

    assert view.overall_score == 0.0
    assert len(view.cards) == 6
    assert view.highlights == []
    assert view.warnings == []


def test_dashboard_completo_copies_every_field_without_recalculation():
    dashboard = _dashboard(
        forecast_confidence=72.0,
        expected_revenue=8000.0,
        overall_progress=0.45,
        average_completion_rate=55.0,
        overall_health=ExecutiveHealth.ATTENTION,
        overall_score=63.0,
        trend_direction=SalesTrendDirection.DOWN,
        pipeline_health=SalesCoachingHealth.ATTENTION,
        highlights=["Alta confiança na previsão"],
        warnings=["Meta distante"],
    )
    service = PresentationService()

    view = service.to_dashboard_view(dashboard)

    assert isinstance(view, DashboardView)
    assert view.title == "Sales Dashboard"
    assert view.overall_health == "attention"
    assert view.overall_score == 63.0
    assert view.highlights == ["Alta confiança na previsão"]
    assert view.warnings == ["Meta distante"]
    assert view.generated_at == dashboard.generated_at

    cards_by_label = {card["label"]: card["value"] for card in view.cards}
    assert cards_by_label["Expected Revenue"] == 8000.0
    assert cards_by_label["Forecast Confidence"] == 72.0
    assert cards_by_label["Target Progress"] == 0.45
    assert cards_by_label["Pipeline Completion"] == 55.0
    assert cards_by_label["Pipeline Health"] == "attention"
    assert cards_by_label["Trend Direction"] == "down"


def test_kpis_preservados_in_the_same_order():
    catalog = SalesKPICatalog(
        kpis=[
            SalesKPI(
                name="Forecast Confidence",
                value=60.0,
                unit="%",
                status="ATTENTION",
                description="Confiança da previsão de receita.",
                generated_at=_T0,
            ),
            SalesKPI(
                name="Trend Direction",
                value="stable",
                unit="texto",
                status="INFO",
                description="Direção da tendência comercial.",
                generated_at=_T0,
            ),
        ],
        overall_score=60.0,
        generated_at=_T0,
    )
    service = PresentationService()

    views = service.to_kpi_views(catalog)

    assert [v.name for v in views] == ["Forecast Confidence", "Trend Direction"]
    assert views[0].value == 60.0
    assert views[0].unit == "%"
    assert views[0].status == "ATTENTION"
    assert views[1].value == "stable"
    assert views[1].unit == "texto"
    assert views[1].status == "INFO"
    assert all(isinstance(v, KPIView) for v in views)


def test_report_preservado_copies_title_subtitle_sections_and_footer():
    sections = [
        SalesReportSection(title="Resumo Executivo", items={"overall_score": 60.0}),
        SalesReportSection(title="Financeiro", items={"expected_revenue": 5000.0}),
    ]
    report_builder = SalesReportBuilder(
        title="Executive Sales Report",
        subtitle=_T0.isoformat(),
        sections=sections,
        footer="Generated automatically by Elevel Prospect AI",
        generated_at=_T0,
    )
    service = PresentationService()

    view = service.to_report_view(report_builder)

    assert isinstance(view, ReportView)
    assert view.title == "Executive Sales Report"
    assert view.subtitle == _T0.isoformat()
    assert view.footer == "Generated automatically by Elevel Prospect AI"
    assert view.sections == sections
    assert view.sections[0] is sections[0]
    assert view.sections[1] is sections[1]


def test_imutabilidade_rejects_attribute_assignment():
    service = PresentationService()
    dashboard_view = service.to_dashboard_view(_dashboard())
    kpi_views = service.to_kpi_views(
        SalesKPICatalog(
            kpis=[
                SalesKPI(
                    name="Forecast Confidence",
                    value=60.0,
                    unit="%",
                    status="ATTENTION",
                    description="d",
                    generated_at=_T0,
                )
            ],
            overall_score=60.0,
            generated_at=_T0,
        )
    )
    report_view = service.to_report_view(
        SalesReportBuilder(
            title="Executive Sales Report",
            subtitle=_T0.isoformat(),
            sections=[],
            footer="Generated automatically by Elevel Prospect AI",
            generated_at=_T0,
        )
    )

    with pytest.raises(ValidationError):
        dashboard_view.overall_score = 0.0

    with pytest.raises(ValidationError):
        kpi_views[0].status = "GOOD"

    with pytest.raises(ValidationError):
        report_view.title = "Alterado"


def test_build_default_presentation_service_returns_a_usable_service():
    service = build_default_presentation_service()

    assert isinstance(service, PresentationService)
    view = service.to_dashboard_view(_dashboard())
    assert isinstance(view, DashboardView)


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(presentation_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(presentation_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(presentation_service)
    assert "CRMEngine" not in source
