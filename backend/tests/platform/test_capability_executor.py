import inspect

import pytest
from pydantic import ValidationError

from app.platform.capabilities import capability_executor, capability_executor_factory
from app.platform.capabilities.capability import Capability
from app.platform.capabilities.capability_executor import CapabilityExecutor
from app.platform.capabilities.capability_executor_factory import (
    build_default_capability_executor,
)
from app.platform.capabilities.capability_manager import CapabilityManager
from app.platform.capabilities.capability_registry import CapabilityRegistry


class _Capability(Capability):
    def __init__(self, label: str, description: str) -> None:
        self.label = label
        self._description = description
        self.description_calls = 0

    def name(self) -> str:
        return self.label

    def description(self) -> str:
        self.description_calls += 1
        return self._description


def _executor(*capabilities: Capability) -> CapabilityExecutor:
    registry = CapabilityRegistry().register_many(list(capabilities))
    manager = CapabilityManager(registry=registry)
    return CapabilityExecutor(manager=manager)


def test_lista_vazia():
    executor = _executor()

    assert executor.execute() == ()


def test_uma_capability():
    capability = _Capability("a", "Description A")
    executor = _executor(capability)

    result = executor.execute()

    assert result == ("Description A",)
    assert capability.description_calls == 1


def test_varias_capabilities():
    capability_a = _Capability("a", "Description A")
    capability_b = _Capability("b", "Description B")
    capability_c = _Capability("c", "Description C")
    executor = _executor(capability_a, capability_b, capability_c)

    result = executor.execute()

    assert result == ("Description A", "Description B", "Description C")
    assert capability_a.description_calls == 1
    assert capability_b.description_calls == 1
    assert capability_c.description_calls == 1


def test_ordem_preservada():
    capability_a = _Capability("a", "first")
    capability_b = _Capability("b", "second")
    executor = _executor(capability_a, capability_b)

    result = executor.execute()

    assert result == ("first", "second")


def test_description_chamado_exatamente_uma_vez_por_capability():
    capability = _Capability("a", "x")
    executor = _executor(capability)

    executor.execute()

    assert capability.description_calls == 1


def test_retorno_preserva_exatamente_a_ordem():
    capability_a = _Capability("a", "1")
    capability_b = _Capability("b", "2")
    capability_c = _Capability("c", "3")
    executor = _executor(capability_a, capability_b, capability_c)

    result = executor.execute()

    assert list(result) == ["1", "2", "3"]


def test_identidade_preservada():
    description = "unique description"
    capability = _Capability("a", description)
    executor = _executor(capability)

    result = executor.execute()

    assert result[0] is description


def test_imutabilidade_rejects_attribute_assignment():
    executor = _executor(_Capability("a", "x"))

    with pytest.raises(ValidationError):
        executor.manager = CapabilityManager(registry=CapabilityRegistry())


def test_injecao_uses_exactly_the_manager_provided():
    manager = CapabilityManager(
        registry=CapabilityRegistry().register(_Capability("a", "x"))
    )

    executor = CapabilityExecutor(manager=manager)

    assert executor.manager is manager


def test_conhece_exclusivamente_capability_manager():
    source = inspect.getsource(capability_executor)

    assert "CapabilityManager" in source
    assert "CapabilityRegistry" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(capability_executor)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(capability_executor)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(capability_executor)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(capability_executor)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(capability_executor)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(capability_executor)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(capability_executor)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(capability_executor)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_capability_executor():
    executor = build_default_capability_executor()

    assert isinstance(executor, CapabilityExecutor)


def test_factory_usa_exclusivamente_build_default_capability_manager():
    source = inspect.getsource(capability_executor_factory)

    assert "build_default_capability_manager" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_manager_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = capability_executor_factory.build_default_capability_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        capability_executor_factory, "build_default_capability_manager", _spy
    )

    build_default_capability_executor()

    assert calls["count"] == 1
