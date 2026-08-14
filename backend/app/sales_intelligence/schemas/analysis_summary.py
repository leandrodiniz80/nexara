from pydantic import BaseModel, Field

from app.sales_intelligence.models.enums import Priority


class AnalysisSummary(BaseModel):
    """Compact, human-readable digest of an AnalysisResult — produced by
    SalesIntelligenceEngine.summary(). Never persisted, purely a read-model."""

    total_score: int = Field(..., ge=0, le=100)
    conversion_probability: int = Field(..., ge=0, le=100)
    priority: Priority
    top_recommendation: str | None = None
    recommendation_count: int
    narrative: str
