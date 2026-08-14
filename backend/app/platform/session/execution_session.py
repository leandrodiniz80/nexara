import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionSession(BaseModel):
    """The unique context of one complete platform execution — frozen, and
    totally immutable: it executes nothing, decides nothing, and knows no
    domain. ExecutionSessionService.finish() never edits an existing
    ExecutionSession, it always returns a new one.
    """

    model_config = ConfigDict(frozen=True)

    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    request_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
