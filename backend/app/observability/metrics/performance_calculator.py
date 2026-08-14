from app.observability.models.execution_statistics import ExecutionStatistics
from app.observability.models.performance_metric import PerformanceMetric

_EMPTY_STATISTICS = ExecutionStatistics(
    total_executions=0,
    successful=0,
    failed=0,
    average_execution_time=0.0,
    max_execution_time=0.0,
    min_execution_time=0.0,
)


class PerformanceCalculator:
    """Deterministic aggregation over a list of PerformanceMetric — total/success/
    failure counts and average/max/min execution_time. Pure function: same input
    list always produces the same ExecutionStatistics, no I/O, no side effects."""

    @staticmethod
    def calculate(metrics: list[PerformanceMetric]) -> ExecutionStatistics:
        if not metrics:
            return _EMPTY_STATISTICS

        total = len(metrics)
        successful = sum(1 for metric in metrics if metric.success)
        execution_times = [metric.execution_time for metric in metrics]

        return ExecutionStatistics(
            total_executions=total,
            successful=successful,
            failed=total - successful,
            average_execution_time=sum(execution_times) / total,
            max_execution_time=max(execution_times),
            min_execution_time=min(execution_times),
        )
