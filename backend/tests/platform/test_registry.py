import pytest

from app.platform.exceptions.platform_exceptions import ModuleNotRegisteredError
from app.platform.models.enums import ModuleType
from app.platform.models.platform_module import PlatformModule
from app.platform.registry.module_descriptor import ModuleDescriptor
from app.platform.registry.module_registry import ModuleRegistry


def _module(module_type: ModuleType, **overrides) -> PlatformModule:
    defaults = dict(name="Workflow", version="1.0.0")
    defaults.update(overrides)
    return PlatformModule(module_type=module_type, descriptor=ModuleDescriptor(**defaults))


def test_register_and_get_round_trip():
    registry = ModuleRegistry()
    module = _module(ModuleType.WORKFLOW)

    registry.register(module)

    assert registry.get(ModuleType.WORKFLOW) is module


def test_get_for_unregistered_type_raises():
    registry = ModuleRegistry()

    with pytest.raises(ModuleNotRegisteredError):
        registry.get(ModuleType.WORKFLOW)


def test_register_again_for_the_same_type_overwrites():
    registry = ModuleRegistry()
    first = _module(ModuleType.WORKFLOW, version="1.0.0")
    second = _module(ModuleType.WORKFLOW, version="2.0.0")
    registry.register(first)

    registry.register(second)

    assert registry.get(ModuleType.WORKFLOW) is second


def test_list_returns_every_registered_module():
    registry = ModuleRegistry()
    workflow = _module(ModuleType.WORKFLOW, name="Workflow")
    automation = _module(ModuleType.AUTOMATION, name="Automation")
    registry.register(workflow)
    registry.register(automation)

    modules = registry.list()

    assert {m.module_type for m in modules} == {ModuleType.WORKFLOW, ModuleType.AUTOMATION}


def test_remove_unregisters_a_module():
    registry = ModuleRegistry()
    registry.register(_module(ModuleType.WORKFLOW))

    registry.remove(ModuleType.WORKFLOW)

    with pytest.raises(ModuleNotRegisteredError):
        registry.get(ModuleType.WORKFLOW)


def test_remove_for_an_unregistered_type_is_a_no_op():
    registry = ModuleRegistry()

    registry.remove(ModuleType.WORKFLOW)
