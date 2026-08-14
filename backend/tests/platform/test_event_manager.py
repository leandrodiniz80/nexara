import inspect

import pytest
from pydantic import ValidationError

from app.platform.events import event_manager, event_manager_factory
from app.platform.events.event_manager import PlatformEventManager
from app.platform.events.event_manager_factory import build_default_event_manager
from app.platform.events.event_registry import EventRegistry
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


def _registry(*events: PlatformEvent) -> EventRegistry:
    return EventRegistry().register_many(list(events))


def test_event_existente():
    event = _EventA()
    manager = PlatformEventManager(registry=_registry(event))

    assert manager.event("event_a") is event


def test_event_inexistente_retorna_none():
    manager = PlatformEventManager(registry=_registry(_EventA()))

    assert manager.event("does_not_exist") is None


def test_exists():
    manager = PlatformEventManager(registry=_registry(_EventA()))

    assert manager.exists("event_a") is True
    assert manager.exists("does_not_exist") is False


def test_events():
    event_a = _EventA()
    event_b = _EventB()
    manager = PlatformEventManager(registry=_registry(event_a, event_b))

    assert manager.events() == [event_a, event_b]


def test_lista_vazia():
    manager = PlatformEventManager(registry=EventRegistry())

    assert manager.events() == []


def test_retorno_preservado():
    event = _EventA()
    manager = PlatformEventManager(registry=_registry(event))

    assert manager.event("event_a") is event
    assert manager.events()[0] is event


def test_event_nunca_executa_ou_publica():
    manager = PlatformEventManager(registry=_registry(_EventA()))

    manager.event("event_a")
    manager.exists("event_a")
    manager.events()

    source = inspect.getsource(event_manager)
    assert "publish" not in source.lower()
    assert "dispatch" not in source.lower()


def test_imutabilidade_rejects_attribute_assignment():
    manager = PlatformEventManager(registry=_registry(_EventA()))

    with pytest.raises(ValidationError):
        manager.registry = EventRegistry()


def test_injecao_uses_exactly_the_registry_provided():
    registry = _registry(_EventA())

    manager = PlatformEventManager(registry=registry)

    assert manager.registry is registry


def test_conhece_exclusivamente_event_registry():
    source = inspect.getsource(event_manager)

    assert "EventRegistry" in source
    assert "PlatformEvent" in source


def test_ausencia_de_runtime():
    source = inspect.getsource(event_manager)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(event_manager)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(event_manager)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(event_manager)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(event_manager)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(event_manager)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(event_manager)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_platform_event_manager():
    manager = build_default_event_manager()

    assert isinstance(manager, PlatformEventManager)


def test_factory_usa_exclusivamente_build_default_event_registry():
    source = inspect.getsource(event_manager_factory)

    assert "build_default_event_registry" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = event_manager_factory.build_default_event_registry

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(event_manager_factory, "build_default_event_registry", _spy)

    build_default_event_manager()

    assert calls["count"] == 1
