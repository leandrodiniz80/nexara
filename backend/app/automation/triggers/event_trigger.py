from app.automation.models.automation import Automation


class EventTrigger:
    """Decides whether an EVENT Automation should fire for the given event name —
    no real EventBus integration this sprint (see app/events for the actual bus);
    the caller is whatever future code subscribes to events and calls
    AutomationEngine.execute_event() with the event's name. Never runs a Workflow
    itself.
    """

    @staticmethod
    def should_fire(automation: Automation, *, event_name: str) -> bool:
        if not automation.enabled:
            return False
        return automation.trigger.event_name == event_name
