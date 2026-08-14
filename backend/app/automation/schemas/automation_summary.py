import uuid
from datetime import datetime

from pydantic import BaseModel

from app.automation.models.automation import Automation
from app.automation.models.enums import AutomationTriggerType


class AutomationSummary(BaseModel):
    """A condensed, read-only view of an Automation definition — what a listing of
    registered automations would show without needing the full trigger/schedule
    detail."""

    automation_id: uuid.UUID
    name: str
    workflow_name: str
    trigger_type: AutomationTriggerType
    enabled: bool
    next_execution: datetime | None
    last_execution: datetime | None

    @classmethod
    def from_automation(cls, automation: Automation) -> "AutomationSummary":
        return cls(
            automation_id=automation.id,
            name=automation.name,
            workflow_name=automation.workflow_name,
            trigger_type=automation.trigger.type,
            enabled=automation.enabled,
            next_execution=automation.schedule.next_execution if automation.schedule else None,
            last_execution=automation.schedule.last_execution if automation.schedule else None,
        )
