import inspect

import pytest
from pydantic import ValidationError

from app.platform.events import event_registry
from app.platform.events.event_registry import EventRegistry
from app.platform.events.event_registry_factory import build_default_event_registry
from app.platform.events.platform_event import PlatformEvent


class _EventA(PlatformEvent):
    def name(self) -> str:
        return "event_a"

    def payload(self) -> object:
        return {"a": 1}


class _EventB(PlatformEvent):
    def name(self) -> str:
        return "event_b"

    def payload(self) -> object:
        return {"b": 2}


class _EventC(PlatformEvent):
    def name(self) -> str:
        return "event_c"

    def payload(self) -> object:
        return None


def test_platform_event_e_abstrato():
    with pytest.raises(TypeError):
        PlatformEvent()


def test_registry_vazio_por_padrao():
    registry = EventRegistry()

    assert registry.list() == []


def test_registro_adds_the_given_event():
    event = _EventA()
    registry = EventRegistry()

    updated = registry.register(event)

    assert updated.list() == [event]
    assert registry.list() == []


def test_register_many_adds_every_given_event_in_order():
    event_a = _EventA()
    event_b = _EventB()
    registry = EventRegistry()

    updated = registry.register_many([event_a, event_b])

    assert updated.list() == [event_a, event_b]


def test_find_existente_returns_the_matching_event():
    event = _EventA()
    registry = EventRegistry().register(event)

    assert registry.find("event_a") is event


def test_find_inexistente_returns_none():
    registry = EventRegistry().register(_EventA())

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = EventRegistry().register(_EventA())

    assert registry.exists("event_a") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = EventRegistry()
    registry = registry.register(_EventA())
    registry = registry.register(_EventB())
    registry = registry.register(_EventC())

    assert [event.name() for event in registry.list()] == ["event_a", "event_b", "event_c"]


def test_register_never_mutates_the_previous_registry():
    original = EventRegistry()

    updated = original.register(_EventA())

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_imutabilidade_rejects_attribute_assignment():
    registry = EventRegistry().register(_EventA())

    with pytest.raises(ValidationError):
        registry.events = ()


def test_registry_usa_exclusivamente_registry_t():
    source = inspect.getsource(event_registry)

    assert "from app.shared.registry.registry import Registry" in source
    assert "for event in" not in source
    assert "for item in" not in source


def test_build_default_event_registry_e_vazio():
    registry = build_default_event_registry()

    assert isinstance(registry, EventRegistry)
    assert registry.list() == []


def test_ausencia_de_runtime():
    source = inspect.getsource(event_registry)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(event_registry)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(event_registry)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(event_registry)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(event_registry)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(event_registry)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(event_registry)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source
