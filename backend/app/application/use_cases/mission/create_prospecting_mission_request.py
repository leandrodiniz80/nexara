import uuid

from pydantic import BaseModel, Field


class CreateProspectingMissionRequest(BaseModel):
    """Input to CreateProspectingMissionUseCase — everything a caller decides,
    nothing the use case derives on its own."""

    mission_name: str
    segment: str
    city: str | None = None
    state: str | None = None
    minimum_score: int = Field(60, ge=0, le=100)
    asset_type: str = "email"
    channel: str | None = None
    tone: str | None = None
    requested_by: uuid.UUID | None = None
