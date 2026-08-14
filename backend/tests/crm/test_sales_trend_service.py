import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.crm.services import sales_trend_service
from app.crm.services.sales_trend import SalesTrend, SalesTrendDirection
from app.crm.services.sales_trend_service import SalesTrendService
from app.crm.services.sales_trend_service_factory import build_default_sales_trend_service
from app.crm.services.sales_trend_snapshot import SalesTrendSnapshot

_T0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _snapshot(
    *,
    timestamp: datetime = _T0,
    expected_revenue: float = 0.0,
    completion_rate: float = 0.0,
    healthy: int = 0,
    attention: int = 0,
    critical: int = 0,
    overall_progress: float = 0.0,
) -> SalesTrendSnapshot:
    return SalesTrendSnapshot(
        timestamp=timestamp,
        expected_revenue=expected_revenue,
        completion_rate=completion_rate,
        healthy=healthy,
        attention=attention,
        critical=critical,
        overall_progress=overall_progress,
    )


def test_snapshot_vazio_yields_zero_deltas_and_a_stable_improving_trend():
    previous = _snapshot(timestamp=_T0)
    current = _snapshot(timestamp=_T1)
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.revenue_delta == 0.0
    assert trend.completion_delta == 0.0
    assert trend.progress_delta == 0.0
    assert trend.health_delta == 0
    assert trend.trend_direction == SalesTrendDirection.STABLE
    assert trend.is_improving is True


def test_crescimento_de_receita_trends_up():
    previous = _snapshot(timestamp=_T0, expected_revenue=1000.0, overall_progress=0.5)
    current = _snapshot(timestamp=_T1, expected_revenue=2000.0, overall_progress=0.6)
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.revenue_delta == 1000.0
    assert trend.trend_direction == SalesTrendDirection.UP


def test_queda_de_receita_trends_down():
    previous = _snapshot(timestamp=_T0, expected_revenue=2000.0)
    current = _snapshot(timestamp=_T1, expected_revenue=1000.0)
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.revenue_delta == -1000.0
    assert trend.trend_direction == SalesTrendDirection.DOWN


def test_estabilidade_when_revenue_does_not_change():
    previous = _snapshot(timestamp=_T0, expected_revenue=1000.0, completion_rate=40.0)
    current = _snapshot(timestamp=_T1, expected_revenue=1000.0, completion_rate=55.0)
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.revenue_delta == 0.0
    assert trend.trend_direction == SalesTrendDirection.STABLE


def test_melhora_geral_marks_is_improving_true():
    previous = _snapshot(
        timestamp=_T0, expected_revenue=1000.0, completion_rate=40.0, overall_progress=0.4
    )
    current = _snapshot(
        timestamp=_T1, expected_revenue=1500.0, completion_rate=50.0, overall_progress=0.5
    )
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.is_improving is True


def test_piora_geral_marks_is_improving_false():
    previous = _snapshot(
        timestamp=_T0, expected_revenue=1000.0, completion_rate=60.0, overall_progress=0.6
    )
    current = _snapshot(
        timestamp=_T1, expected_revenue=1500.0, completion_rate=50.0, overall_progress=0.6
    )
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.completion_delta == -10.0
    assert trend.is_improving is False


def test_delta_zero_when_current_equals_previous():
    snapshot = _snapshot(
        timestamp=_T0,
        expected_revenue=5000.0,
        completion_rate=70.0,
        healthy=3,
        attention=1,
        critical=0,
        overall_progress=0.8,
    )
    service = SalesTrendService()

    trend = service.compare(snapshot, snapshot, now=_T1)

    assert trend.revenue_delta == 0.0
    assert trend.completion_delta == 0.0
    assert trend.progress_delta == 0.0
    assert trend.health_delta == 0


def test_valores_negativos_are_computed_correctly():
    previous = _snapshot(
        timestamp=_T0,
        expected_revenue=5000.0,
        completion_rate=80.0,
        healthy=5,
        overall_progress=0.9,
    )
    current = _snapshot(
        timestamp=_T1,
        expected_revenue=3000.0,
        completion_rate=60.0,
        healthy=2,
        overall_progress=0.7,
    )
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    assert trend.revenue_delta == -2000.0
    assert trend.completion_delta == -20.0
    assert trend.progress_delta == pytest.approx(-0.2)
    assert trend.health_delta == -3
    assert trend.trend_direction == SalesTrendDirection.DOWN
    assert trend.is_improving is False


def test_imutabilidade_rejects_attribute_assignment():
    previous = _snapshot(timestamp=_T0)
    current = _snapshot(timestamp=_T1, expected_revenue=1000.0)
    service = SalesTrendService()

    trend = service.compare(previous, current, now=_T1)

    with pytest.raises(ValidationError):
        trend.is_improving = False


def test_build_default_sales_trend_service_returns_a_usable_service():
    service = build_default_sales_trend_service()
    previous = _snapshot(timestamp=_T0)
    current = _snapshot(timestamp=_T1, expected_revenue=1000.0, overall_progress=0.1)

    assert isinstance(service, SalesTrendService)
    trend = service.compare(previous, current, now=_T1)
    assert isinstance(trend, SalesTrend)
    assert trend.trend_direction == SalesTrendDirection.UP


def test_nenhuma_dependencia_de_runtime():
    source = inspect.getsource(sales_trend_service)
    assert "Runtime" not in source


def test_nenhuma_dependencia_de_workflow():
    source = inspect.getsource(sales_trend_service)
    assert "Workflow" not in source


def test_nenhuma_dependencia_de_crm_engine():
    source = inspect.getsource(sales_trend_service)
    assert "CRMEngine" not in source
