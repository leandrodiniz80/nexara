import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services import sales_kpi_service
from app.crm.services.executive_sales_dashboard import ExecutiveHealth, ExecutiveSalesDashboard
from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_kpi_catalog import SalesKPICatalog
from app.crm.services.sales_kpi_service import SalesKPIService
from app.crm.services.sales_kpi_service_factory import build_default_sales_kpi_service
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
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
        overall_health=SalesCoachingHealth.HEALTHY,
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
        highlights=[],
        warnings=[],
    )


def _kpi(catalog: SalesKPICatalog, name: str):
    return next(k for k in catalog.kpis if k.name == name)


def test_dashboard_vazio_yields_zeroed_numeric_kpis():
    dashboard = _dashboard(
        forecast_confidence=0.0,
        expected_revenue=0.0,
        overall_progress=0.0,
        average_completion_rate=0.0,
        overall_score=0.0,
    )
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    assert _kpi(catalog, "Forecast Confidence").value == 0.0
    assert _kpi(catalog, "Target Progress").value == 0.0
    assert _kpi(catalog, "Pipeline Completion").value == 0.0
    assert _kpi(catalog, "Revenue Forecast").value == 0.0
    assert _kpi(catalog, "Forecast Confidence").status == "CRITICAL"


def test_todos_os_kpis_are_created_with_the_exact_names():
    dashboard = _dashboard()
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    names = [kpi.name for kpi in catalog.kpis]
    assert names == [
        "Forecast Confidence",
        "Target Progress",
        "Pipeline Completion",
        "Revenue Forecast",
        "Pipeline Health",
        "Trend Direction",
    ]


def test_status_good_when_indicator_is_at_least_75_percent():
    dashboard = _dashboard(forecast_confidence=80.0)
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    assert _kpi(catalog, "Forecast Confidence").status == "GOOD"


def test_status_attention_when_indicator_is_between_50_and_75_percent():
    dashboard = _dashboard(forecast_confidence=60.0)
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    assert _kpi(catalog, "Forecast Confidence").status == "ATTENTION"


def test_status_critical_when_indicator_is_below_50_percent():
    dashboard = _dashboard(forecast_confidence=30.0)
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    assert _kpi(catalog, "Forecast Confidence").status == "CRITICAL"


def test_kpis_textuais_are_always_info_and_carry_the_raw_label():
    dashboard = _dashboard(
        overall_health=ExecutiveHealth.CRITICAL, trend_direction=SalesTrendDirection.DOWN
    )
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    pipeline_health = _kpi(catalog, "Pipeline Health")
    trend_direction = _kpi(catalog, "Trend Direction")
    assert pipeline_health.status == "INFO"
    assert pipeline_health.unit == "texto"
    assert pipeline_health.value == "critical"
    assert trend_direction.status == "INFO"
    assert trend_direction.unit == "texto"
    assert trend_direction.value == "down"


def test_overall_score_is_copied_through_without_recalculation():
    dashboard = _dashboard(overall_score=63.5)
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    assert catalog.overall_score == 63.5


def test_imutabilidade_rejects_attribute_assignment():
    dashboard = _dashboard()
    service = SalesKPIService()

    catalog = service.build(dashboard, now=_T0)

    with pytest.raises(ValidationError):
        catalog.overall_score = 0.0

    with pytest.raises(ValidationError):
        catalog.kpis[0].status = "GOOD"


def test_build_default_sales_kpi_service_returns_a_usable_service():
    service = build_default_sales_kpi_service()
    dashboard = _dashboard()

    assert isinstance(service, SalesKPIService)
    catalog = service.build(dashboard, now=_T0)
    assert isinstance(catalog, SalesKPICatalog)
    assert len(catalog.kpis) == 6


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_kpi_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_kpi_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_kpi_service)
    assert "CRMEngine" not in source
