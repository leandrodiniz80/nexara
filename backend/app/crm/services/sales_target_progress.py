from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.crm.services.sales_target import SalesTarget


class SalesTargetProgress(BaseModel):
    """The frozen outcome of comparing a SalesForecast/SalesPipelineSummary
    against one SalesTarget — how close (or past) the goal the commercial
    operation currently stands. SalesTargetService always returns a new
    one; it never edits a previous SalesTargetProgress in place.

    `current_revenue`/`current_opportunities` are raw counts, unbounded.
    Every other progress figure — `current_conversion_rate`,
    `revenue_progress`, `opportunity_progress`, `conversion_progress`,
    `overall_progress` — is a fraction clamped to the 0..1 range.
    """

    model_config = ConfigDict(frozen=True)

    target: SalesTarget
    current_revenue: float
    current_opportunities: int
    current_conversion_rate: float
    revenue_progress: float
    opportunity_progress: float
    conversion_progress: float
    overall_progress: float
    is_completed: bool
    generated_at: datetime
