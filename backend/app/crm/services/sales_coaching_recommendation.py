from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SalesCoachingRecommendation(BaseModel):
    """One deterministic operational suggestion produced by
    SalesCoachingService — frozen, like every other record type in this
    platform: a recommendation is never edited after being generated, only
    ever regenerated fresh from the metrics/benchmark that produced it.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    description: str
    priority: str
    category: str
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)
