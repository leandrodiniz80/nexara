from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict


class SalesBenchmarkResult(BaseModel):
    """The frozen outcome of comparing one execution's SalesExecutionMetrics
    against a population of others — how it stacks up, nothing about how it
    got there. SalesBenchmarkService always returns a new one; it never
    edits a previous SalesBenchmarkResult in place.
    """

    model_config = ConfigDict(frozen=True)

    average_completion_rate: float
    average_duration: timedelta | None = None
    best_completion_rate: float
    worst_completion_rate: float
    fastest_duration: timedelta | None = None
    slowest_duration: timedelta | None = None
    ranking_position: int
    total_compared: int
    above_average: bool
    generated_at: datetime
