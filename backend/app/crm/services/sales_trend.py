import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SalesTrendDirection(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class SalesTrend(BaseModel):
    """The frozen outcome of comparing two SalesTrendSnapshots — how
    commercial performance moved between them, nothing about how either
    snapshot was measured. SalesTrendService always returns a new one; it
    never edits a previous SalesTrend in place.
    """

    model_config = ConfigDict(frozen=True)

    trend_direction: SalesTrendDirection
    revenue_delta: float
    completion_delta: float
    progress_delta: float
    health_delta: int
    is_improving: bool
    generated_at: datetime
