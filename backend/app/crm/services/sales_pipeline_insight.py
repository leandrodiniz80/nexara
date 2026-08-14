from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SalesPipelineInsight(BaseModel):
    """One deterministic observation about the pipeline as a whole — frozen,
    like every other record type in this platform: an insight is never
    edited after being generated, only ever regenerated fresh from the
    SalesCoachingResult population that produced it.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    description: str
    severity: str
    affected_opportunities: int
    metadata: dict[str, Any] = Field(default_factory=dict)
