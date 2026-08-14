import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_forecast import SalesForecast
from app.crm.services.sales_pipeline_summary import SalesPipelineSummary
from app.crm.services.sales_target_progress import SalesTargetProgress
from app.crm.services.sales_trend import SalesTrend


class ExecutiveHealth(str, enum.Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ATTENTION = "attention"
    CRITICAL = "critical"


class ExecutiveSalesDashboard(BaseModel):
    """The frozen, consolidated executive view of the CRM — just an
    aggregation of what SalesForecastService, SalesTargetService,
    SalesPipelineIntelligenceService and SalesTrendService already
    computed, plus a single score/health verdict and a deterministic list
    of highlights/warnings derived from them. No new business calculation
    lives here beyond that aggregation.
    """

    model_config = ConfigDict(frozen=True)

    forecast: SalesForecast
    target_progress: SalesTargetProgress
    pipeline_summary: SalesPipelineSummary
    trend: SalesTrend
    generated_at: datetime
    overall_health: ExecutiveHealth
    overall_score: float
    highlights: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
