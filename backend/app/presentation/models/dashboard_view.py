from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DashboardView(BaseModel):
    """A plain, serialization-ready view of an ExecutiveSalesDashboard —
    frozen: every field here is a direct copy of a value
    ExecutiveSalesDashboardService already computed, never recalculated.
    Built for future interfaces (API, Web, Mobile, PDF, HTML, Export) to
    consume instead of the domain object itself.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    overall_health: str
    overall_score: float
    cards: list[dict[str, Any]] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
