from app.automation.exceptions.base import AutomationError


class AutomationNotFoundError(AutomationError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No automation registered with name '{name}'.")


class AutomationNotTriggeredError(AutomationError):
    """Raised when execute_manual()/execute_scheduled()/execute_event()/
    execute_condition() is called but the Automation is disabled, or its Trigger
    decided the conditions to fire aren't met right now. Not a failure — a "there
    was nothing to do" signal distinct from the Workflow it would have run failing.
    """

    def __init__(self, name: str, trigger_type: str) -> None:
        self.name = name
        self.trigger_type = trigger_type
        super().__init__(
            f"Automation '{name}' was not triggered ({trigger_type}: conditions not met)."
        )
