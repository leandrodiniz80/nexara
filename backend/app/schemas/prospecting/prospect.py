import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.prospecting.enums import (
    ProspectOrigin,
    ProspectPriority,
    ProspectStage,
    ProspectStatus,
    ProspectTemperature,
)
from app.schemas.common import AuditSchema


class ProspectBase(BaseModel):
    """Fields a caller may set when opening an opportunity.

    Lifecycle fields (status, score, temperature, current_stage, qualified_at,
    converted_at, lost_at, reason_lost, last_interaction_at) are intentionally absent:
    they are only ever mutated through Prospect Engine methods, never written directly.
    """

    company_id: uuid.UUID
    campaign_id: uuid.UUID
    mission_id: uuid.UUID
    owner_id: uuid.UUID | None = None
    origin: ProspectOrigin | None = None
    priority: ProspectPriority = ProspectPriority.NORMAL
    estimated_value: Decimal | None = Field(None, ge=0)
    probability: int | None = Field(None, ge=0, le=100)
    notes: str | None = None


class ProspectCreate(ProspectBase):
    pass


class ProspectUpdate(BaseModel):
    owner_id: uuid.UUID | None = None
    priority: ProspectPriority | None = None
    estimated_value: Decimal | None = Field(None, ge=0)
    probability: int | None = Field(None, ge=0, le=100)
    notes: str | None = None


class ProspectRead(ProspectBase, AuditSchema):
    status: ProspectStatus
    score: int | None = Field(None, ge=0, le=100)
    temperature: ProspectTemperature
    current_stage: ProspectStage
    qualified_at: datetime | None = None
    converted_at: datetime | None = None
    lost_at: datetime | None = None
    last_interaction_at: datetime | None = None
    next_action_at: datetime | None = None
    reason_lost: str | None = None
