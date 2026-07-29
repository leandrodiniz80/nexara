import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import AuditSchema


class MissionEventBase(BaseModel):
    mission_id: uuid.UUID
    event: str
    description: str | None = None
    event_metadata: dict[str, Any] | None = None
    occurred_at: datetime


class MissionEventCreate(MissionEventBase):
    pass


class MissionEventRead(MissionEventBase, AuditSchema):
    pass
