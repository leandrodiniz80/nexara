import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.crm.models.enums import ActivityType


class CRMActivity(BaseModel):
    """One logged interaction against a CRMOpportunity — a call, an email, a
    meeting note. `opportunity_id` is a bare reference, never the full
    CRMOpportunity embedded.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    opportunity_id: uuid.UUID
    type: ActivityType
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
