import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.prospecting.enums import InteractionType
from app.schemas.common import AuditSchema


class InteractionBase(BaseModel):
    prospect_id: uuid.UUID
    contact_id: uuid.UUID | None = None
    type: InteractionType
    notes: str | None = None
    occurred_at: datetime
    result: str | None = None
    next_follow_up_at: datetime | None = None


class InteractionCreate(InteractionBase):
    pass


class InteractionUpdate(BaseModel):
    contact_id: uuid.UUID | None = None
    type: InteractionType | None = None
    notes: str | None = None
    occurred_at: datetime | None = None
    result: str | None = None
    next_follow_up_at: datetime | None = None


class InteractionRead(InteractionBase, AuditSchema):
    pass
