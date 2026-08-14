import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.automation.models.automation_schedule import AutomationSchedule
from app.automation.models.automation_trigger import AutomationTrigger


class Automation(BaseModel):
    """A named binding of "which Workflow" to "what triggers it" — the definition,
    not a run of it (that's AutomationExecution). Mutable, unlike Workflow: `enabled`
    is meant to be toggled in place (AutomationRegistry.enable()/disable()), and a
    SCHEDULED automation's `schedule.next_execution`/`last_execution` update as time
    passes — there is no versioning concept here the way Workflow has.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    workflow_name: str
    trigger: AutomationTrigger
    schedule: AutomationSchedule | None = None
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
