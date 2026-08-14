import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SchedulerTick(BaseModel):
    """The result of one Scheduler.tick(now) call — which registered Automations
    were found due to run, and when the tick itself happened. Just a report:
    nothing here executes anything."""

    ticked_at: datetime
    due_automation_ids: list[uuid.UUID] = Field(default_factory=list)
