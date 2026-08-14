from datetime import datetime

from app.automation.models.enums import AutomationTriggerType
from app.automation.registry.automation_registry import AutomationRegistry
from app.automation.scheduler.scheduler_tick import SchedulerTick
from app.automation.triggers.scheduled_trigger import ScheduledTrigger


class Scheduler:
    """Infrastructure only — no real cron, no asyncio, no threads, no background
    worker. tick(now) is a pure, synchronous check: "given this instant, which
    registered SCHEDULED Automations are due?" It never executes a Workflow, and
    never even calls AutomationEngine — whatever calls tick() decides what to do
    with the due automation ids it reports (typically: call
    AutomationEngine.execute_scheduled() for each one).
    """

    def __init__(self, registry: AutomationRegistry) -> None:
        self.registry = registry

    def tick(self, now: datetime) -> SchedulerTick:
        due_ids = [
            automation.id
            for automation in self.registry.list()
            if automation.trigger.type == AutomationTriggerType.SCHEDULED
            and ScheduledTrigger.should_fire(automation, now=now)
        ]
        return SchedulerTick(ticked_at=now, due_automation_ids=due_ids)
