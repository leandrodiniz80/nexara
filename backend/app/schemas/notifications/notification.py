import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID | None
    message: str
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    """GET /notifications — unread_count is a separate COUNT(*), not
    len(data): data is capped at `limit`, so counting the page itself would
    undercount whenever there are more unread notifications than the page
    can hold."""

    data: list[NotificationResponse]
    unread_count: int
