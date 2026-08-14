import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services import sales_report_service
from app.crm.services.executive_sales_dashboard import ExecutiveHealth, ExecutiveSalesDashboard
from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_kpi import SalesKPI
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_report import SalesReport
from app.crm.services.sales_report_service import SalesReportService
from app.crm.services.sales_report_service_factory import build_default_sales_report_service
from app.crm.services.sales_target import SalesTarget
from app.crm.services.sales_target_progress import SalesTargetProgress
from app.crm.services.sales_trend import SalesTrend, SalesTrendDirection

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _target() -> SalesTarget:
    return SalesTarget(
        name="Meta Q1",
        period="2026-Q1",
        target_revenue=10000.0,
        target_opportunities=10,
        target_conversion_rate=0.7,
        created_at=_T0,
    )


def _dashboard(
    *,
    forecast_confidence: float = 60.0,
    expected_revenue: float = 5000.0,
    overall_progress: float = 0.6,
    average_completion_rate: float = 60.0,
    overall_health: ExecutiveHealth = ExecutiveHealth.GOOD,
    overall_score: float = 60.0,
    trend_direction: SalesTrendDirection = SalesTrendDirection.STABLE,
    highlights: list[str] | None = None,
    warnings: list[str] | None = None,
    pipeline_health: SalesCoachingHealth = SalesCoachingHealth.HEALTHY,
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
    target_progress = SalesTargetProgress(
        target=_target(),
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


def _kpis(items: list[SalesKPI] | None = None) -> SalesKPICatalog:
    kpis = items if items is not None else [
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
    ]
    return SalesKPICatalog(kpis=kpis, overall_score=60.0, generated_at=_T0)


def _section(report: SalesReport, title: str):
    return next(s for s in report.sections if s.title == title)


def test_relatorio_vazio_still_builds_four_sections():
    dashboard = _dashboard(
        forecast_confidence=0.0,
        expected_revenue=0.0,
        overall_progress=0.0,
        average_completion_rate=0.0,
        overall_score=0.0,
    )
    kpis = _kpis(items=[])
    service = SalesReportService()

    report = service.build(dashboard, kpis, now=_T0)

    assert len(report.sections) == 4
    assert _section(report, "Indicadores").items["kpis"] == []


def test_quatro_secoes_are_created():
    service = SalesReportService()

    report = service.build(_dashboard(), _kpis(), now=_T0)

    assert len(report.sections) == 4


def test_ordem_correta_of_the_sections():
    service = SalesReportService()

    report = service.build(_dashboard(), _kpis(), now=_T0)

    assert [section.title for section in report.sections] == [
        "Resumo Executivo",
        "Financeiro",
        "Pipeline",
        "Indicadores",
    ]


def test_conteudo_correto_of_each_section():
    dashboard = _dashboard(
        forecast_confidence=72.0,
        expected_revenue=8000.0,
        overall_progress=0.45,
        average_completion_rate=55.0,
        overall_health=ExecutiveHealth.ATTENTION,
        overall_score=63.0,
        trend_direction=SalesTrendDirection.DOWN,
        highlights=["Alta confiança na previsão"],
        warnings=["Meta distante"],
        pipeline_health=SalesCoachingHealth.ATTENTION,
    )
    service = SalesReportService()

    report = service.build(dashboard, _kpis(), now=_T0)

    resumo = _section(report, "Resumo Executivo")
    assert resumo.items["overall_health"] == ExecutiveHealth.ATTENTION
    assert resumo.items["overall_score"] == 63.0
    assert resumo.items["highlights"] == ["Alta confiança na previsão"]
    assert resumo.items["warnings"] == ["Meta distante"]

    financeiro = _section(report, "Financeiro")
    assert financeiro.items["expected_revenue"] == 8000.0
    assert financeiro.items["forecast_confidence"] == 72.0
    assert financeiro.items["target_progress"] == 0.45

    pipeline = _section(report, "Pipeline")
    assert pipeline.items["pipeline_health"] == SalesCoachingHealth.ATTENTION
    assert pipeline.items["completion_rate"] == 55.0
    assert pipeline.items["trend_direction"] == SalesTrendDirection.DOWN


def test_kpis_preservados_in_the_same_order():
    kpi_a = SalesKPI(
        name="Forecast Confidence",
        value=60.0,
        unit="%",
        status="ATTENTION",
        description="Confiança da previsão de receita.",
        generated_at=_T0,
    )
    kpi_b = SalesKPI(
        name="Revenue Forecast",
        value=8000.0,
        unit="R$",
        status="GOOD",
        description="Receita esperada com base na previsão atual.",
        generated_at=_T0,
    )
    kpis = _kpis(items=[kpi_a, kpi_b])
    service = SalesReportService()

    report = service.build(_dashboard(), kpis, now=_T0)

    assert _section(report, "Indicadores").items["kpis"] == [kpi_a, kpi_b]
    assert report.kpis is kpis


def test_imutabilidade_rejects_attribute_assignment():
    service = SalesReportService()

    report = service.build(_dashboard(), _kpis(), now=_T0)

    with pytest.raises(ValidationError):
        report.generated_at = _T0

    with pytest.raises(ValidationError):
        report.sections[0].title = "Alterado"


def test_build_default_sales_report_service_returns_a_usable_service():
    service = build_default_sales_report_service()

    assert isinstance(service, SalesReportService)
    report = service.build(_dashboard(), _kpis(), now=_T0)
    assert isinstance(report, SalesReport)
    assert len(report.sections) == 4


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_report_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_report_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_report_service)
    assert "CRMEngine" not in source
