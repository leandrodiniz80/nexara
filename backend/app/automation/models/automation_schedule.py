from datetime import datetime

from pydantic import BaseModel


class AutomationSchedule(BaseModel):
    """When a SCHEDULED Automation should next/last have run. `cron_expression` is
    stored as-is — this sprint parses no cron syntax (Scheduler.tick() compares
    `next_execution` to a given instant directly; computing the *next*
    next_execution from the cron expression is left for a future sprint that
    actually needs it). Mutable: Scheduler/ScheduledTrigger update
    next_execution/last_execution as time passes.
    """

    cron_expression: str
    timezone: str = "UTC"
    next_execution: datetime | None = None
    last_execution: datetime | None = None
