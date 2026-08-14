from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SalesTarget(BaseModel):
    """A commercial goal for one period — frozen, the definition, not the
    tracking of it (that's SalesTargetProgress). `target_conversion_rate`
    is a fraction between 0.0 and 1.0 (e.g. 0.7 for a 70% goal), the same
    0..1 scale SalesTargetProgress's own conversion fields use.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    period: str
    target_revenue: float
    target_opportunities: int
    target_conversion_rate: float
    created_at: datetime
