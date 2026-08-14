import inspect

import pytest
from pydantic import ValidationError

from app.platform.events import event_executor, event_executor_factory
from app.platform.events.event_executor import PlatformEventExecutor
from app.platform.events.event_executor_factory import build_default_event_executor
from app.platform.events.event_manager import PlatformEventManager
from app.platform.events.event_registry import EventRegistry
from app.platform.events.platform_event import PlatformEvent


class _Event(PlatformEvent):
    def __init__(self, label: str, payload: object) -> None:
        self.label = label
        self._payload = payload
        self.payload_calls = 0

    def name(self) -> str:
        return self.label

    def payload(self) -> object:
        self.payload_calls += 1
        return self._payload


def _executor(*events: PlatformEvent) -> PlatformEventExecutor:
    registry = EventRegistry().register_many(list(events))
    manager = PlatformEventManager(registry=registry)
    return PlatformEventExecutor(manager=manager)


def test_lista_vazia():
    executor = _executor()

    assert executor.execute() == ()


def test_um_evento():
    payload = {"a": 1}
    event = _Event("a", payload)
    executor = _executor(event)

    result = executor.execute()

    assert result == (payload,)
    assert event.payload_calls == 1


def test_varios_eventos():
    event_a = _Event("a", {"a": 1})
    event_b = _Event("b", {"b": 2})
    event_c = _Event("c", {"c": 3})
    executor = _executor(event_a, event_b, event_c)

    result = executor.execute()

    assert result == ({"a": 1}, {"b": 2}, {"c": 3})
    assert event_a.payload_calls == 1
    assert event_b.payload_calls == 1
    assert event_c.payload_calls == 1


def test_ordem_preservada():
    event_a = _Event("a", "first")
    event_b = _Event("b", "second")
    executor = _executor(event_a, event_b)

    result = executor.execute()

    assert result == ("first", "second")


def test_payload_chamado_exatamente_uma_vez_por_evento():
    event = _Event("a", "x")
    executor = _executor(event)

    executor.execute()

    assert event.payload_calls == 1


def test_retorno_preserva_exatamente_a_ordem():
    event_a = _Event("a", 1)
    event_b = _Event("b", 2)
    event_c = _Event("c", 3)
    executor = _executor(event_a, event_b, event_c)

    result = executor.execute()

    assert list(result) == [1, 2, 3]


def test_identidade_preservada():
    payload = object()
    event = _Event("a", payload)
    executor = _executor(event)

    result = executor.execute()

    assert result[0] is payload


def test_imutabilidade_rejects_attribute_assignment():
    executor = _executor(_Event("a", 1))

    with pytest.raises(ValidationError):
        executor.manager = PlatformEventManager(registry=EventRegistry())


def test_injecao_uses_exactly_the_manager_provided():
    manager = PlatformEventManager(registry=EventRegistry().register(_Event("a", 1)))

    executor = PlatformEventExecutor(manager=manager)

    assert executor.manager is manager


def test_conhece_exclusivamente_platform_event_manager():
    source = inspect.getsource(event_executor)

    assert "PlatformEventManager" in source
    assert "EventRegistry" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(event_executor)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(event_executor)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(event_executor)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(event_executor)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(event_executor)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(event_executor)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(event_executor)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_platform_event_executor():
    executor = build_default_event_executor()

    assert isinstance(executor, PlatformEventExecutor)


def test_factory_usa_exclusivamente_build_default_event_manager():
    source = inspect.getsource(event_executor_factory)

    assert "build_default_event_manager" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_manager_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = event_executor_factory.build_default_event_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(event_executor_factory, "build_default_event_manager", _spy)

    build_default_event_executor()

    assert calls["count"] == 1
