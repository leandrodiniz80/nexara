import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.crm.services.sales_benchmark_result import SalesBenchmarkResult
from app.crm.services.sales_coaching_recommendation import SalesCoachingRecommendation


class SalesCoachingHealth(str, enum.Enum):
    HEALTHY = "healthy"
    ATTENTION = "attention"
    CRITICAL = "critical"


class SalesCoachingResult(BaseModel):
    """The frozen outcome of coaching one execution — the benchmark it was
    measured against, the deterministic recommendations produced from it,
    and an overall health verdict. SalesCoachingService always returns a
    new one; it never edits a previous SalesCoachingResult in place.
    """

    model_config = ConfigDict(frozen=True)

    benchmark: SalesBenchmarkResult
    recommendations: list[SalesCoachingRecommendation] = Field(default_factory=list)
    overall_health: SalesCoachingHealth
    generated_at: datetime
