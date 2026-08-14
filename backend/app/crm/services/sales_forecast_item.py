from pydantic import BaseModel, ConfigDict

from app.crm.models.crm_opportunity import CRMOpportunity


class SalesForecastItem(BaseModel):
    """One opportunity's contribution to the revenue forecast — frozen: a
    forecast item is never edited after being computed, only ever
    regenerated fresh from the opportunity/pipeline that produced it.
    """

    model_config = ConfigDict(frozen=True)

    opportunity: CRMOpportunity
    probability: float
    expected_revenue: float
    confidence: float
    reason: str
