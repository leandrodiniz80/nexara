import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services import sales_target_service
from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_target import SalesTarget
from app.crm.services.sales_target_progress import SalesTargetProgress
from app.crm.services.sales_target_service import SalesTargetService
from app.crm.services.sales_target_service_factory import build_default_sales_target_service

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _target(
    *,
    target_revenue: float = 10000.0,
    target_opportunities: int = 10,
    target_conversion_rate: float = 0.7,
) -> SalesTarget:
    return SalesTarget(
        name="Meta Q1",
        period="2026-Q1",
        target_revenue=target_revenue,
        target_opportunities=target_opportunities,
        target_conversion_rate=target_conversion_rate,
        created_at=_T0,
    )


def _forecast(*, expected_revenue: float = 0.0) -> SalesForecast:
    return SalesForecast(
        total_pipeline_value=0.0,
        expected_revenue=expected_revenue,
        average_probability=0.0,
        forecast_confidence=0.0,
        won_value=0.0,
        lost_value=0.0,
        open_value=0.0,
        forecast_items=[],
        generated_at=_T0,
    )


def _pipeline_summary(
    *, total_opportunities: int = 0, average_completion_rate: float = 0.0
) -> SalesPipelineSummary:
    return SalesPipelineSummary(
        total_opportunities=total_opportunities,
        healthy=0,
        attention=0,
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


def test_meta_vazia_is_trivially_completed():
    target = _target(target_revenue=0.0, target_opportunities=0, target_conversion_rate=0.0)
    forecast = _forecast()
    pipeline = _pipeline_summary()
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.revenue_progress == 1.0
    assert progress.opportunity_progress == 1.0
    assert progress.conversion_progress == 1.0
    assert progress.overall_progress == 1.0
    assert progress.is_completed is True


def test_meta_atingida_exactly_reaches_every_dimension():
    target = _target(target_revenue=10000.0, target_opportunities=10, target_conversion_rate=0.7)
    forecast = _forecast(expected_revenue=10000.0)
    pipeline = _pipeline_summary(total_opportunities=10, average_completion_rate=70.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.revenue_progress == 1.0
    assert progress.opportunity_progress == 1.0
    assert progress.conversion_progress == 1.0
    assert progress.overall_progress == 1.0
    assert progress.is_completed is True


def test_meta_parcialmente_atingida_is_not_completed():
    target = _target(target_revenue=10000.0, target_opportunities=10, target_conversion_rate=0.7)
    forecast = _forecast(expected_revenue=5000.0)
    pipeline = _pipeline_summary(total_opportunities=5, average_completion_rate=35.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.revenue_progress == pytest.approx(0.5)
    assert progress.opportunity_progress == pytest.approx(0.5)
    assert progress.conversion_progress == pytest.approx(0.5)
    assert progress.overall_progress == pytest.approx(0.5)
    assert progress.is_completed is False


def test_meta_superada_clamps_progress_at_one():
    target = _target(target_revenue=10000.0, target_opportunities=10, target_conversion_rate=0.5)
    forecast = _forecast(expected_revenue=25000.0)
    pipeline = _pipeline_summary(total_opportunities=25, average_completion_rate=100.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.current_revenue == 25000.0
    assert progress.current_opportunities == 25
    assert progress.revenue_progress == 1.0
    assert progress.opportunity_progress == 1.0
    assert progress.conversion_progress == 1.0
    assert progress.overall_progress == 1.0
    assert progress.is_completed is True


def test_receita_zero_yields_no_revenue_progress():
    target = _target()
    forecast = _forecast(expected_revenue=0.0)
    pipeline = _pipeline_summary(total_opportunities=10, average_completion_rate=70.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.current_revenue == 0.0
    assert progress.revenue_progress == 0.0


def test_pipeline_vazio_yields_no_opportunity_or_conversion_progress():
    target = _target()
    forecast = _forecast(expected_revenue=10000.0)
    pipeline = _pipeline_summary()
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.current_opportunities == 0
    assert progress.opportunity_progress == 0.0
    assert progress.current_conversion_rate == 0.0
    assert progress.conversion_progress == 0.0


def test_forecast_vazio_yields_no_revenue_progress():
    target = _target()
    forecast = _forecast()
    pipeline = _pipeline_summary(total_opportunities=10, average_completion_rate=70.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    assert progress.current_revenue == 0.0
    assert progress.revenue_progress == 0.0


def test_limites_0_1_never_exceed_the_expected_range():
    target = _target(target_revenue=100.0, target_opportunities=1, target_conversion_rate=0.1)
    forecast = _forecast(expected_revenue=999999.0)
    pipeline = _pipeline_summary(total_opportunities=999, average_completion_rate=100.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    for value in (
        progress.current_conversion_rate,
        progress.revenue_progress,
        progress.opportunity_progress,
        progress.conversion_progress,
        progress.overall_progress,
    ):
        assert 0.0 <= value <= 1.0


def test_overall_progress_is_the_simple_average_of_the_three_dimensions():
    target = _target(target_revenue=10000.0, target_opportunities=10, target_conversion_rate=0.8)
    forecast = _forecast(expected_revenue=10000.0)
    pipeline = _pipeline_summary(total_opportunities=5, average_completion_rate=40.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    expected = (1.0 + 0.5 + 0.5) / 3
    assert progress.overall_progress == pytest.approx(expected)


def test_imutabilidade_rejects_attribute_assignment():
    target = _target()
    forecast = _forecast(expected_revenue=10000.0)
    pipeline = _pipeline_summary(total_opportunities=10, average_completion_rate=70.0)
    service = SalesTargetService()

    progress = service.evaluate(target, forecast, pipeline, now=_T0)

    with pytest.raises(ValidationError):
        progress.is_completed = False

    with pytest.raises(ValidationError):
        progress.target = _target(target_revenue=1.0)


def test_build_default_sales_target_service_returns_a_usable_service():
    service = build_default_sales_target_service()
    target = _target()
    forecast = _forecast(expected_revenue=10000.0)
    pipeline = _pipeline_summary(total_opportunities=10, average_completion_rate=70.0)

    assert isinstance(service, SalesTargetService)
    progress = service.evaluate(target, forecast, pipeline, now=_T0)
    assert isinstance(progress, SalesTargetProgress)
    assert progress.is_completed is True


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_target_service)
    assert "CRMEngine" not in source


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_target_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_target_service)
    assert "Workflow" not in source
