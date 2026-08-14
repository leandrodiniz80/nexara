import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services import executive_sales_dashboard_service
from app.crm.services.executive_sales_dashboard import ExecutiveHealth, ExecutiveSalesDashboard
from app.crm.services.executive_sales_dashboard_service import ExecutiveSalesDashboardService
from app.crm.services.executive_sales_dashboard_service_factory import (
    build_default_executive_sales_dashboard_service,
)
from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_forecast import SalesForecast
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


def _target_progress(
    *, overall_progress: float = 0.5, is_completed: bool = False
) -> SalesTargetProgress:
    return SalesTargetProgress(
        target=_target(),
        current_revenue=5000.0,
        current_opportunities=5,
        current_conversion_rate=0.35,
        revenue_progress=0.5,
        opportunity_progress=0.5,
        conversion_progress=0.5,
        overall_progress=overall_progress,
        is_completed=is_completed,
        generated_at=_T0,
    )


def _forecast(*, forecast_confidence: float = 70.0) -> SalesForecast:
    return SalesForecast(
        total_pipeline_value=10000.0,
        expected_revenue=5000.0,
        average_probability=0.5,
        forecast_confidence=forecast_confidence,
        won_value=0.0,
        lost_value=0.0,
        open_value=10000.0,
        forecast_items=[],
        generated_at=_T0,
    )


def _pipeline_summary(
    *,
    average_completion_rate: float = 60.0,
    healthy: int = 3,
    attention: int = 1,
    critical: int = 0,
) -> SalesPipelineSummary:
    return SalesPipelineSummary(
        total_opportunities=healthy + attention + critical,
        healthy=healthy,
        attention=attention,
        critical=critical,
        average_completion_rate=average_completion_rate,
        average_duration=None,
        total_pauses=0,
        total_rollbacks=0,
        total_finished=0,
        overall_health=SalesCoachingHealth.HEALTHY,
        insights=[],
        generated_at=_T0,
    )


def _trend(
    *,
    trend_direction: SalesTrendDirection = SalesTrendDirection.STABLE,
    is_improving: bool = True,
) -> SalesTrend:
    return SalesTrend(
        trend_direction=trend_direction,
        revenue_delta=0.0,
        completion_delta=0.0,
        progress_delta=0.0,
        health_delta=0,
        is_improving=is_improving,
        generated_at=_T0,
    )


def test_dashboard_vazio_scores_zero_and_is_critical():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=0.0),
        _target_progress(overall_progress=0.0),
        _pipeline_summary(average_completion_rate=0.0),
        _trend(is_improving=False),
        now=_T0,
    )

    assert dashboard.overall_score == 0.0
    assert dashboard.overall_health == ExecutiveHealth.CRITICAL
    assert dashboard.highlights == []


def test_pipeline_saudavel_scores_high():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=95.0),
        _target_progress(overall_progress=0.95),
        _pipeline_summary(average_completion_rate=95.0),
        _trend(),
        now=_T0,
    )

    assert dashboard.overall_score == pytest.approx(95.0)
    assert dashboard.overall_health == ExecutiveHealth.EXCELLENT


def test_pipeline_critico_scores_low():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=10.0),
        _target_progress(overall_progress=0.1),
        _pipeline_summary(average_completion_rate=10.0),
        _trend(),
        now=_T0,
    )

    assert dashboard.overall_health == ExecutiveHealth.CRITICAL


def test_meta_atingida_adds_a_highlight():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(),
        _target_progress(overall_progress=1.0, is_completed=True),
        _pipeline_summary(),
        _trend(),
        now=_T0,
    )

    assert "Meta atingida" in dashboard.highlights


def test_meta_distante_adds_a_warning():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(),
        _target_progress(overall_progress=0.3),
        _pipeline_summary(),
        _trend(),
        now=_T0,
    )

    assert "Meta distante" in dashboard.warnings


def test_pipeline_crescendo_adds_a_highlight():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(),
        _target_progress(),
        _pipeline_summary(),
        _trend(is_improving=True),
        now=_T0,
    )

    assert "Pipeline crescendo" in dashboard.highlights


def test_pipeline_em_queda_adds_a_warning():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(),
        _target_progress(),
        _pipeline_summary(),
        _trend(trend_direction=SalesTrendDirection.DOWN, is_improving=False),
        now=_T0,
    )

    assert "Pipeline em queda" in dashboard.warnings


def test_forecast_alto_adds_a_highlight():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=85.0),
        _target_progress(),
        _pipeline_summary(),
        _trend(),
        now=_T0,
    )

    assert "Alta confiança na previsão" in dashboard.highlights


def test_forecast_baixo_adds_a_warning():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=20.0),
        _target_progress(),
        _pipeline_summary(),
        _trend(),
        now=_T0,
    )

    assert "Baixa confiança na previsão" in dashboard.warnings


def test_overall_score_is_the_simple_average_of_the_three_inputs():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=60.0),
        _target_progress(overall_progress=0.9),
        _pipeline_summary(average_completion_rate=30.0),
        _trend(),
        now=_T0,
    )

    expected = (60.0 + 90.0 + 30.0) / 3
    assert dashboard.overall_score == pytest.approx(expected)


def test_overall_health_thresholds():
    service = ExecutiveSalesDashboardService()

    excellent = service.build(
        _forecast(forecast_confidence=90.0),
        _target_progress(overall_progress=0.9),
        _pipeline_summary(average_completion_rate=90.0),
        _trend(),
        now=_T0,
    )
    good = service.build(
        _forecast(forecast_confidence=75.0),
        _target_progress(overall_progress=0.75),
        _pipeline_summary(average_completion_rate=75.0),
        _trend(),
        now=_T0,
    )
    attention = service.build(
        _forecast(forecast_confidence=50.0),
        _target_progress(overall_progress=0.5),
        _pipeline_summary(average_completion_rate=50.0),
        _trend(),
        now=_T0,
    )
    critical = service.build(
        _forecast(forecast_confidence=49.0),
        _target_progress(overall_progress=0.49),
        _pipeline_summary(average_completion_rate=49.0),
        _trend(),
        now=_T0,
    )

    assert excellent.overall_health == ExecutiveHealth.EXCELLENT
    assert good.overall_health == ExecutiveHealth.GOOD
    assert attention.overall_health == ExecutiveHealth.ATTENTION
    assert critical.overall_health == ExecutiveHealth.CRITICAL


def test_highlights_accumulate_every_matching_condition():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=90.0),
        _target_progress(overall_progress=1.0, is_completed=True),
        _pipeline_summary(),
        _trend(is_improving=True),
        now=_T0,
    )

    assert set(dashboard.highlights) == {
        "Meta atingida",
        "Pipeline crescendo",
        "Alta confiança na previsão",
    }


def test_warnings_accumulate_every_matching_condition():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(forecast_confidence=10.0),
        _target_progress(overall_progress=0.1, is_completed=False),
        _pipeline_summary(),
        _trend(trend_direction=SalesTrendDirection.DOWN, is_improving=False),
        now=_T0,
    )

    assert set(dashboard.warnings) == {
        "Pipeline em queda",
        "Meta distante",
        "Baixa confiança na previsão",
    }


def test_imutabilidade_rejects_attribute_assignment():
    service = ExecutiveSalesDashboardService()

    dashboard = service.build(
        _forecast(), _target_progress(), _pipeline_summary(), _trend(), now=_T0
    )

    with pytest.raises(ValidationError):
        dashboard.overall_score = 0.0

    with pytest.raises(ValidationError):
        dashboard.highlights = ["hacked"]


def test_build_default_executive_sales_dashboard_service_returns_a_usable_service():
    service = build_default_executive_sales_dashboard_service()

    assert isinstance(service, ExecutiveSalesDashboardService)
    dashboard = service.build(
        _forecast(), _target_progress(), _pipeline_summary(), _trend(), now=_T0
    )
    assert isinstance(dashboard, ExecutiveSalesDashboard)


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(executive_sales_dashboard_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(executive_sales_dashboard_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(executive_sales_dashboard_service)
    assert "CRMEngine" not in source
