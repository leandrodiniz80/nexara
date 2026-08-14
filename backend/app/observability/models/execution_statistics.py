from pydantic import BaseModel, ConfigDict


class ExecutionStatistics(BaseModel):
    """A fresh aggregate snapshot computed by PerformanceCalculator from whatever
    PerformanceMetrics currently exist — frozen because it's a point-in-time
    computation result, never mutated once built (recomputing means building a new
    one, not updating this one)."""

    model_config = ConfigDict(frozen=True)

    total_executions: int
    successful: int
    failed: int
    average_execution_time: float
    max_execution_time: float
    min_execution_time: float
