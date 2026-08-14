import pytest

from app.automation.exceptions.automation_exceptions import AutomationNotFoundError
from app.automation.models.automation import Automation
from app.automation.models.automation_trigger import AutomationTrigger
from app.automation.models.enums import AutomationTriggerType
from app.automation.registry.automation_registry import AutomationRegistry


def _automation(**overrides) -> Automation:
    defaults = dict(
        name="Test Automation",
        workflow_name="Test Workflow",
        trigger=AutomationTrigger(type=AutomationTriggerType.MANUAL),
    )
    defaults.update(overrides)
    return Automation(**defaults)


def test_register_and_get_round_trip():
    registry = AutomationRegistry()
    automation = _automation()

    registry.register(automation)

    assert registry.get("Test Automation") is automation


def test_get_unknown_name_raises():
    registry = AutomationRegistry()

    with pytest.raises(AutomationNotFoundError):
        registry.get("Does Not Exist")


def test_list_returns_every_registered_automation():
    registry = AutomationRegistry()
    registry.register(_automation(name="A"))
    registry.register(_automation(name="B"))

    names = {a.name for a in registry.list()}

    assert names == {"A", "B"}


def test_disable_then_enable_round_trip():
    registry = AutomationRegistry()
    automation = _automation()
    registry.register(automation)

    disabled = registry.disable("Test Automation")
    assert disabled.enabled is False
    assert automation.enabled is False  # mutated in place

    enabled = registry.enable("Test Automation")
    assert enabled.enabled is True


def test_enable_unknown_name_raises():
    registry = AutomationRegistry()

    with pytest.raises(AutomationNotFoundError):
        registry.enable("Does Not Exist")


def test_registering_a_new_automation_with_the_same_name_replaces_it():
    registry = AutomationRegistry()
    first = _automation(workflow_name="Workflow A")
    second = _automation(workflow_name="Workflow B")

    registry.register(first)
    registry.register(second)

    assert registry.get("Test Automation").workflow_name == "Workflow B"
    assert len(registry.list()) == 1
