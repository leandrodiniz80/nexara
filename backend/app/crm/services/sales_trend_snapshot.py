from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SalesTrendSnapshot(BaseModel):
    """A frozen, point-in-time capture of commercial performance — just the
    handful of figures SalesTrendService compares between two moments in
    time. Building one is its caller's responsibility (typically read
    straight off a SalesForecast/SalesPipelineSummary/SalesTargetProgress
    taken at that moment); this type itself knows nothing about how those
    were computed.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    expected_revenue: float
    completion_rate: float
    healthy: int
    attention: int
    critical: int
    overall_progress: float
