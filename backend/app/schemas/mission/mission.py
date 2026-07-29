import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.mission.enums import MissionPriority, MissionStatus
from app.schemas.common import AuditSchema


class MissionBase(BaseModel):
    """Fields a caller may set when defining a mission's objective/targets.

    Lifecycle fields (status, progress, estimated_completion, started_at, finished_at)
    are intentionally absent: they are only ever mutated through MissionEngine methods.
    """

    name: str = Field(..., max_length=255)
    description: str | None = None
    objective: str | None = None
    priority: MissionPriority = MissionPriority.NORMAL
    target_segment: str | None = Field(None, max_length=120)
    target_region: str | None = Field(None, max_length=120)
    target_city: str | None = Field(None, max_length=120)
    target_state: str | None = Field(None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    target_quantity: int | None = Field(None, ge=0)
    target_meetings: int | None = Field(None, ge=0)
    target_contracts: int | None = Field(None, ge=0)
    target_revenue: Decimal | None = Field(None, ge=0)
    deadline: date | None = None
    owner_id: uuid.UUID | None = None


class MissionCreate(MissionBase):
    pass


class MissionUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    objective: str | None = None
    priority: MissionPriority | None = None
    target_segment: str | None = Field(None, max_length=120)
    target_region: str | None = Field(None, max_length=120)
    target_city: str | None = Field(None, max_length=120)
    target_state: str | None = Field(None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    target_quantity: int | None = Field(None, ge=0)
    target_meetings: int | None = Field(None, ge=0)
    target_contracts: int | None = Field(None, ge=0)
    target_revenue: Decimal | None = Field(None, ge=0)
    deadline: date | None = None
    owner_id: uuid.UUID | None = None


class MissionRead(MissionBase, AuditSchema):
    status: MissionStatus
    progress: int | None = Field(None, ge=0, le=100)
    estimated_completion: date | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
