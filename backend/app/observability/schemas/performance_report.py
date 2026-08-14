from pydantic import BaseModel, Field

from app.observability.models.execution_statistics import ExecutionStatistics
from app.observability.models.performance_metric import PerformanceMetric


class PerformanceReport(BaseModel):
    """ExecutionStatistics plus the raw PerformanceMetrics they were computed
    from — `component=None` means "across every component", matching
    MetricsService.build_statistics()'s own optional filter."""

    component: str | None
    statistics: ExecutionStatistics
    metrics: list[PerformanceMetric] = Field(default_factory=list)
