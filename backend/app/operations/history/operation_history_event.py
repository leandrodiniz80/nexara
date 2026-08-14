from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperationHistoryEvent(BaseModel):
    """One fact that happened during an Operation's lifecycle — frozen: an
    event is never edited after being recorded, only ever added alongside.
    """

    model_config = ConfigDict(frozen=True)

    event_type: str
    timestamp: datetime
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
