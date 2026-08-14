from pydantic import BaseModel

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.commercial_score import CommercialScore
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.models.recommendation import Recommendation


class AnalysisResult(BaseModel):
    """Everything SalesIntelligenceEngine.analyze_company()/analyze_prospect() produce
    for one CommercialProfile in a single call."""

    profile: CommercialProfile
    strategy_used: CommercialSegment
    score: CommercialScore
    recommendations: list[Recommendation]
