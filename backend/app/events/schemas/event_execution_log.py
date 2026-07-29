import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class EventExecutionLog(BaseModel):
    """One audit-trail row for a single handler's reaction to a single event. Recorded
    by EventBus.dispatch() for every handler it calls, success or failure alike — a
    handler raising never takes down the bus or the other subscribers of the same event.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_id: uuid.UUID
    event_name: str
    handler: str
    execution_time: float
    success: bool
    error: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
