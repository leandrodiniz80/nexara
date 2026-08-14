from app.observability.models.performance_metric import PerformanceMetric


class MetricsCollector:
    """Deterministic construction of PerformanceMetric — a pure function of its
    inputs (aside from the timestamp it stamps), same role as AuditBuilder/
    TraceBuilder.build_step()."""

    @staticmethod
    def collect(
        *,
        component: str,
        operation: str,
        execution_time: float,
        success: bool,
        memory_usage: float | None = None,
        cpu_usage: float | None = None,
    ) -> PerformanceMetric:
        return PerformanceMetric(
            component=component,
            operation=operation,
            execution_time=execution_time,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success=success,
        )
