from app.observability.metrics.metrics_collector import MetricsCollector
from app.observability.metrics.metrics_service import MetricsService
from app.observability.metrics.performance_calculator import PerformanceCalculator
from app.observability.repositories.observability_repository import ObservabilityRepository


def test_metrics_collector_builds_a_frozen_metric():
    metric = MetricsCollector.collect(
        component="CopyAgent", operation="generate", execution_time=1.5, success=True
    )

    assert metric.component == "CopyAgent"
    assert metric.execution_time == 1.5
    assert metric.success is True
    assert metric.memory_usage is None
    assert metric.cpu_usage is None


def test_performance_calculator_on_empty_list_returns_zeroed_statistics():
    statistics = PerformanceCalculator.calculate([])

    assert statistics.total_executions == 0
    assert statistics.successful == 0
    assert statistics.failed == 0
    assert statistics.average_execution_time == 0.0
    assert statistics.max_execution_time == 0.0
    assert statistics.min_execution_time == 0.0


def test_performance_calculator_aggregates_multiple_metrics():
    metrics = [
        MetricsCollector.collect(component="X", operation="op", execution_time=1.0, success=True),
        MetricsCollector.collect(component="X", operation="op", execution_time=3.0, success=True),
        MetricsCollector.collect(component="X", operation="op", execution_time=2.0, success=False),
    ]

    statistics = PerformanceCalculator.calculate(metrics)

    assert statistics.total_executions == 3
    assert statistics.successful == 2
    assert statistics.failed == 1
    assert statistics.average_execution_time == 2.0
    assert statistics.max_execution_time == 3.0
    assert statistics.min_execution_time == 1.0


def test_performance_calculator_is_deterministic():
    metrics = [
        MetricsCollector.collect(component="X", operation="op", execution_time=1.0, success=True)
    ]

    first = PerformanceCalculator.calculate(metrics)
    second = PerformanceCalculator.calculate(metrics)

    assert first == second


def test_metrics_service_record_persists_through_the_repository():
    repository = ObservabilityRepository()
    service = MetricsService(repository)

    service.record(component="CopyAgent", operation="generate", execution_time=1.0, success=True)

    assert len(repository.list_metrics()) == 1


def test_metrics_service_build_statistics_filters_by_component():
    repository = ObservabilityRepository()
    service = MetricsService(repository)
    service.record(component="CopyAgent", operation="generate", execution_time=1.0, success=True)
    service.record(component="OutreachEngine", operation="submit", execution_time=5.0, success=True)

    statistics = service.build_statistics(component="CopyAgent")

    assert statistics.total_executions == 1
    assert statistics.average_execution_time == 1.0


def test_metrics_service_build_report_includes_the_underlying_metrics():
    repository = ObservabilityRepository()
    service = MetricsService(repository)
    service.record(component="CopyAgent", operation="generate", execution_time=1.0, success=True)

    report = service.build_report(component="CopyAgent")

    assert report.component == "CopyAgent"
    assert len(report.metrics) == 1
    assert report.statistics.total_executions == 1
