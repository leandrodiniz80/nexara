import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SalesTimelineEvent(BaseModel):
    """One fact that happened during an opportunity's commercial journey —
    frozen, like every other record type in this platform: once recorded,
    an event is never edited, only ever added alongside.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at: datetime
    event_type: str
    description: str
    step_number: int | None = None
    step_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
