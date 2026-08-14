from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.sales_intelligence.models.enums import Priority


class Recommendation(BaseModel):
    """One actionable suggestion produced by RecommendationEngine. Plain data — this
    module never acts on its own recommendations (no email sending, no scheduling);
    it only describes what should happen and why."""

    title: str
    description: str
    priority: Priority
    confidence: int = Field(..., ge=0, le=100)
    reason: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
