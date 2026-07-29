import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditSchema(BaseModel):
    """Read-only audit columns shared by every entity's response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    created_by: uuid.UUID | None = None
    updated_by: uuid.UUID | None = None
