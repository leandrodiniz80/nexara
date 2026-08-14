from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.automation.models.enums import AutomationTriggerType


class AutomationTrigger(BaseModel):
    """What kind of trigger fires an Automation, plus whatever minimal config that
    type needs to be evaluated — `event_name` for EVENT, `condition` for CONDITION.
    Frozen: changing how an Automation is triggered is a new configuration, not a
    mutation of the running one (the same reasoning as WorkflowStep).

    `condition` is a free-form string description, not an evaluated expression —
    this sprint builds no condition-evaluation engine; ConditionTrigger only checks
    a boolean its caller already computed elsewhere.
    """

    model_config = ConfigDict(frozen=True)

    type: AutomationTriggerType
    event_name: str | None = None
    condition: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
