from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.mission.enums import MissionStatus
from app.schemas.mission.enums import PipelineHealth


class MissionSummary(BaseModel):
    """Computed, read-only snapshot returned by MissionEngine.summary(). Never persisted."""

    model_config = ConfigDict(from_attributes=True)

    status: MissionStatus
    progress: int = Field(..., ge=0, le=100)
    days_remaining: int | None = None
    total_prospects: int
    qualified: int
    meetings: int
    contracts: int
    estimated_revenue: Decimal
    pipeline_health: PipelineHealth
    next_recommended_action: str
