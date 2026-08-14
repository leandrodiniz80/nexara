from datetime import datetime

from app.automation.models.automation import Automation


class ScheduledTrigger:
    """Decides whether a SCHEDULED Automation is due — pure comparison of `now`
    against `automation.schedule.next_execution`, no cron parsing, no clock of its
    own. Never runs a Workflow itself.
    """

    @staticmethod
    def should_fire(automation: Automation, *, now: datetime) -> bool:
        if not automation.enabled or automation.schedule is None:
            return False
        if automation.schedule.next_execution is None:
            return False
        return now >= automation.schedule.next_execution
