import pytest

from app.observability.metrics.metrics_collector import MetricsCollector
from app.observability.metrics.performance_calculator import PerformanceCalculator
from app.observability.models.execution_statistics import ExecutionStatistics


def test_execution_statistics_is_frozen():
    statistics = ExecutionStatistics(
        total_executions=1,
        successful=1,
        failed=0,
        average_execution_time=1.0,
        max_execution_time=1.0,
        min_execution_time=1.0,
    )

    with pytest.raises(Exception):
        statistics.total_executions = 2


def test_single_metric_statistics_have_equal_average_max_and_min():
    metric = MetricsCollector.collect(
        component="X", operation="op", execution_time=4.2, success=True
    )

    statistics = PerformanceCalculator.calculate([metric])

    assert statistics.total_executions == 1
    assert statistics.average_execution_time == 4.2
    assert statistics.max_execution_time == 4.2
    assert statistics.min_execution_time == 4.2


def test_all_failed_statistics_report_zero_successful():
    metrics = [
        MetricsCollector.collect(component="X", operation="op", execution_time=1.0, success=False),
        MetricsCollector.collect(component="X", operation="op", execution_time=2.0, success=False),
    ]

    statistics = PerformanceCalculator.calculate(metrics)

    assert statistics.total_executions == 2
    assert statistics.successful == 0
    assert statistics.failed == 2


def test_all_successful_statistics_report_zero_failed():
    metrics = [
        MetricsCollector.collect(component="X", operation="op", execution_time=1.0, success=True),
        MetricsCollector.collect(component="X", operation="op", execution_time=2.0, success=True),
    ]

    statistics = PerformanceCalculator.calculate(metrics)

    assert statistics.successful == 2
    assert statistics.failed == 0


def test_statistics_total_always_equals_successful_plus_failed():
    metrics = [
        MetricsCollector.collect(component="X", operation="op", execution_time=1.0, success=True),
        MetricsCollector.collect(component="X", operation="op", execution_time=2.0, success=False),
        MetricsCollector.collect(component="X", operation="op", execution_time=3.0, success=True),
    ]

    statistics = PerformanceCalculator.calculate(metrics)

    assert statistics.total_executions == statistics.successful + statistics.failed
