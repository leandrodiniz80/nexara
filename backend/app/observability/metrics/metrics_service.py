from app.observability.metrics.metrics_collector import MetricsCollector
from app.observability.metrics.performance_calculator import PerformanceCalculator
from app.observability.models.execution_statistics import ExecutionStatistics
from app.observability.models.performance_metric import PerformanceMetric
from app.observability.repositories.observability_repository import ObservabilityRepository
from app.observability.schemas.performance_report import PerformanceReport


class MetricsService:
    """Records PerformanceMetrics and builds aggregates from them — execution
    time, error/warning counts (via `success`), average/max/min time — by
    delegating construction to MetricsCollector and aggregation to
    PerformanceCalculator. Owns no arithmetic of its own.
    """

    def __init__(
        self,
        repository: ObservabilityRepository,
        collector: MetricsCollector | None = None,
        calculator: PerformanceCalculator | None = None,
    ) -> None:
        self.repository = repository
        self.collector = collector or MetricsCollector()
        self.calculator = calculator or PerformanceCalculator()

    def record(
        self,
        *,
        component: str,
        operation: str,
        execution_time: float,
        success: bool,
        memory_usage: float | None = None,
        cpu_usage: float | None = None,
    ) -> PerformanceMetric:
        metric = self.collector.collect(
            component=component,
            operation=operation,
            execution_time=execution_time,
            success=success,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
        )
        return self.repository.save_metric(metric)

    def build_statistics(
        self, *, component: str | None = None, operation: str | None = None
    ) -> ExecutionStatistics:
        metrics = self.repository.list_metrics(component=component, operation=operation)
        return self.calculator.calculate(metrics)

    def build_report(self, *, component: str | None = None) -> PerformanceReport:
        metrics = self.repository.list_metrics(component=component)
        statistics = self.calculator.calculate(metrics)
        return PerformanceReport(component=component, statistics=statistics, metrics=metrics)
