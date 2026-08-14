from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_coaching_result import SalesCoachingHealth
from app.crm.services.sales_pipeline_insight import SalesPipelineInsight


class SalesPipelineSummary(BaseModel):
    """The frozen, consolidated view of an entire pipeline's commercial
    health — counts by health tier, pipeline-wide averages and totals, the
    deterministic insights derived from them, and an overall verdict.
    SalesPipelineIntelligenceService always returns a new one; it never
    edits a previous SalesPipelineSummary in place.
    """

    model_config = ConfigDict(frozen=True)

    total_opportunities: int
    healthy: int
    attention: int
    critical: int
    average_completion_rate: float
    average_duration: timedelta | None = None
    total_pauses: int
    total_rollbacks: int
    total_finished: int
    overall_health: SalesCoachingHealth
    insights: list[SalesPipelineInsight] = Field(default_factory=list)
    generated_at: datetime
