from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict


class SalesExecutionMetrics(BaseModel):
    """A frozen snapshot of measurements taken over one enrollment's
    SalesCadenceExecution and SalesTimeline at a single point in time.
    Nothing here is persisted or recomputed later; a caller who wants fresh
    metrics asks SalesExecutionAnalyticsService for a new snapshot.
    """

    model_config = ConfigDict(frozen=True)

    total_steps: int
    completed_steps: int
    remaining_steps: int
    completion_rate: float
    total_events: int
    pause_count: int
    resume_count: int
    rollback_count: int
    finished: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_duration: timedelta | None = None
