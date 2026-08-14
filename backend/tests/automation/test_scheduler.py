from datetime import datetime, timedelta, timezone

from app.automation.models.automation import Automation
from app.automation.models.automation_schedule import AutomationSchedule
from app.automation.models.automation_trigger import AutomationTrigger
from app.automation.models.enums import AutomationTriggerType
from app.automation.registry.automation_registry import AutomationRegistry
from app.automation.scheduler.scheduler import Scheduler
from app.automation.scheduler.scheduler_clock import SchedulerClock


def _scheduled_automation(name: str, *, next_execution, enabled: bool = True) -> Automation:
    return Automation(
        name=name,
        workflow_name="Test Workflow",
        enabled=enabled,
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(cron_expression="0 8 * * *", next_execution=next_execution),
    )


def test_tick_reports_due_automations():
    now = datetime.now(timezone.utc)
    registry = AutomationRegistry()
    due = _scheduled_automation("Due", next_execution=now - timedelta(minutes=1))
    not_due = _scheduled_automation("Not Due", next_execution=now + timedelta(hours=1))
    registry.register(due)
    registry.register(not_due)
    scheduler = Scheduler(registry)

    tick = scheduler.tick(now)

    assert tick.due_automation_ids == [due.id]
    assert tick.ticked_at == now


def test_tick_ignores_disabled_automations():
    now = datetime.now(timezone.utc)
    registry = AutomationRegistry()
    registry.register(_scheduled_automation("Disabled", next_execution=now, enabled=False))
    scheduler = Scheduler(registry)

    tick = scheduler.tick(now)

    assert tick.due_automation_ids == []


def test_tick_ignores_non_scheduled_automations():
    now = datetime.now(timezone.utc)
    registry = AutomationRegistry()
    manual = Automation(
        name="Manual",
        workflow_name="Test Workflow",
        trigger=AutomationTrigger(type=AutomationTriggerType.MANUAL),
    )
    registry.register(manual)
    scheduler = Scheduler(registry)

    tick = scheduler.tick(now)

    assert tick.due_automation_ids == []


def test_tick_with_no_registered_automations_returns_empty():
    scheduler = Scheduler(AutomationRegistry())

    tick = scheduler.tick(datetime.now(timezone.utc))

    assert tick.due_automation_ids == []


def test_tick_is_deterministic_given_the_same_instant():
    now = datetime.now(timezone.utc)
    registry = AutomationRegistry()
    registry.register(_scheduled_automation("Due", next_execution=now - timedelta(minutes=1)))
    scheduler = Scheduler(registry)

    first = scheduler.tick(now)
    second = scheduler.tick(now)

    assert first.due_automation_ids == second.due_automation_ids


def test_scheduler_clock_now_returns_a_timezone_aware_datetime():
    now = SchedulerClock.now()

    assert now.tzinfo is not None
