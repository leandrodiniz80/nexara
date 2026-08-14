from datetime import datetime, timedelta, timezone

from app.automation.models.automation import Automation
from app.automation.models.automation_schedule import AutomationSchedule
from app.automation.models.automation_trigger import AutomationTrigger
from app.automation.models.enums import AutomationTriggerType
from app.automation.triggers.condition_trigger import ConditionTrigger
from app.automation.triggers.event_trigger import EventTrigger
from app.automation.triggers.manual_trigger import ManualTrigger
from app.automation.triggers.scheduled_trigger import ScheduledTrigger


def _automation(**overrides) -> Automation:
    defaults = dict(
        name="Test",
        workflow_name="Test Workflow",
        trigger=AutomationTrigger(type=AutomationTriggerType.MANUAL),
    )
    defaults.update(overrides)
    return Automation(**defaults)


def test_manual_trigger_fires_when_enabled():
    assert ManualTrigger.should_fire(_automation(enabled=True)) is True


def test_manual_trigger_never_fires_when_disabled():
    assert ManualTrigger.should_fire(_automation(enabled=False)) is False


def test_scheduled_trigger_fires_when_now_is_past_next_execution():
    now = datetime.now(timezone.utc)
    automation = _automation(
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(
            cron_expression="0 8 * * *", next_execution=now - timedelta(minutes=1)
        ),
    )

    assert ScheduledTrigger.should_fire(automation, now=now) is True


def test_scheduled_trigger_does_not_fire_before_next_execution():
    now = datetime.now(timezone.utc)
    automation = _automation(
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(
            cron_expression="0 8 * * *", next_execution=now + timedelta(hours=1)
        ),
    )

    assert ScheduledTrigger.should_fire(automation, now=now) is False


def test_scheduled_trigger_does_not_fire_without_a_schedule():
    automation = _automation(trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED))

    assert ScheduledTrigger.should_fire(automation, now=datetime.now(timezone.utc)) is False


def test_scheduled_trigger_does_not_fire_without_next_execution_set():
    automation = _automation(
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(cron_expression="0 8 * * *"),
    )

    assert ScheduledTrigger.should_fire(automation, now=datetime.now(timezone.utc)) is False


def test_scheduled_trigger_never_fires_when_disabled():
    now = datetime.now(timezone.utc)
    automation = _automation(
        enabled=False,
        trigger=AutomationTrigger(type=AutomationTriggerType.SCHEDULED),
        schedule=AutomationSchedule(
            cron_expression="0 8 * * *", next_execution=now - timedelta(minutes=1)
        ),
    )

    assert ScheduledTrigger.should_fire(automation, now=now) is False


def test_event_trigger_fires_for_a_matching_event_name():
    automation = _automation(
        trigger=AutomationTrigger(
            type=AutomationTriggerType.EVENT, event_name="prospect_qualified"
        )
    )

    assert EventTrigger.should_fire(automation, event_name="prospect_qualified") is True


def test_event_trigger_does_not_fire_for_a_different_event_name():
    automation = _automation(
        trigger=AutomationTrigger(
            type=AutomationTriggerType.EVENT, event_name="prospect_qualified"
        )
    )

    assert EventTrigger.should_fire(automation, event_name="mission_created") is False


def test_condition_trigger_fires_only_when_condition_met_and_enabled():
    automation = _automation(trigger=AutomationTrigger(type=AutomationTriggerType.CONDITION))

    assert ConditionTrigger.should_fire(automation, condition_met=True) is True
    assert ConditionTrigger.should_fire(automation, condition_met=False) is False


def test_condition_trigger_never_fires_when_disabled_even_if_condition_met():
    automation = _automation(
        enabled=False, trigger=AutomationTrigger(type=AutomationTriggerType.CONDITION)
    )

    assert ConditionTrigger.should_fire(automation, condition_met=True) is False
