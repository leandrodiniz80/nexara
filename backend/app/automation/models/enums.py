import enum


class AutomationTriggerType(str, enum.Enum):
    """Closed vocabulary for AutomationTrigger.type — the four ways an Automation
    can be told to run, matching this sprint's four Trigger classes one-to-one."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    CONDITION = "condition"


class AutomationStatus(str, enum.Enum):
    """Closed vocabulary for AutomationExecution.status. Unlike WorkflowExecution,
    there is no PAUSED state here — an AutomationExecution wraps exactly one
    WorkflowEngine.execute() call, not a resumable multi-step sequence of its own."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
