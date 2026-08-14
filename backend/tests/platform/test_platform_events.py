import inspect

import pytest
from pydantic import ValidationError

from app.platform.events import platform_events, platform_events_factory
from app.platform.events.event_executor import PlatformEventExecutor
from app.platform.events.event_manager import PlatformEventManager
from app.platform.events.event_registry import EventRegistry
from app.platform.events.platform_event import PlatformEvent
from app.platform.events.platform_events import PlatformEvents
from app.platform.events.platform_events_factory import build_default_platform_events


class _Event(PlatformEvent):
    def __init__(self, label: str, payload: object) -> None:
        self.label = label
        self._payload = payload

    def name(self) -> str:
        return self.label

    def payload(self) -> object:
        return self._payload


def _platform_events(*events: PlatformEvent) -> PlatformEvents:
    registry = EventRegistry().register_many(list(events))
    manager = PlatformEventManager(registry=registry)
    executor = PlatformEventExecutor(manager=manager)
    return PlatformEvents(executor=executor)


def test_events_retorna_exatamente_executor_execute():
    events = _platform_events(_Event("a", 1), _Event("b", 2))

    assert events.events() == (1, 2)


def test_identidade_preservada(monkeypatch):
    sentinel = (object(),)

    def _fake_execute(self):
        return sentinel

    monkeypatch.setattr(PlatformEventExecutor, "execute", _fake_execute)

    events = _platform_events()

    assert events.events() is sentinel


def test_execute_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformEventExecutor.execute

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformEventExecutor, "execute", _spy)

    events = _platform_events(_Event("a", 1))
    events.events()

    assert calls["count"] == 1


def test_nenhuma_reconstrucao(monkeypatch):
    calls = {"count": 0}
    original = PlatformEventExecutor.execute

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformEventExecutor, "execute", _spy)

    events = _platform_events(_Event("a", 1))
    events.events()
    events.events()

    assert calls["count"] == 2


def test_imutabilidade_rejects_attribute_assignment():
    events = _platform_events()

    with pytest.raises(ValidationError):
        events.executor = PlatformEventExecutor(
            manager=PlatformEventManager(registry=EventRegistry())
        )


def test_injecao_uses_exactly_the_executor_provided():
    executor = PlatformEventExecutor(
        manager=PlatformEventManager(registry=EventRegistry())
    )

    events = PlatformEvents(executor=executor)

    assert events.executor is executor


def test_conhece_exclusivamente_platform_event_executor():
    source = inspect.getsource(platform_events)

    assert "PlatformEventExecutor" in source
    assert "PlatformEventManager" not in source
    assert "EventRegistry" not in source
    assert "PlatformEvent(" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(platform_events)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(platform_events)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(platform_events)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(platform_events)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(platform_events)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(platform_events)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(platform_events)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_platform_events():
    events = build_default_platform_events()

    assert isinstance(events, PlatformEvents)


def test_factory_usa_exclusivamente_build_default_event_executor():
    source = inspect.getsource(platform_events_factory)

    assert "build_default_event_executor" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_executor_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = platform_events_factory.build_default_event_executor

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(platform_events_factory, "build_default_event_executor", _spy)

    build_default_platform_events()

    assert calls["count"] == 1
