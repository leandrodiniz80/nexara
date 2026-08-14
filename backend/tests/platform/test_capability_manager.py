import inspect

import pytest
from pydantic import ValidationError

from app.platform.capabilities import capability_manager, capability_manager_factory
from app.platform.capabilities.capability import Capability
from app.platform.capabilities.capability_manager import CapabilityManager
from app.platform.capabilities.capability_manager_factory import (
    build_default_capability_manager,
)
from app.platform.capabilities.capability_registry import CapabilityRegistry


class _CapabilityA(Capability):
    def __init__(self) -> None:
        self.description_calls = 0

    def name(self) -> str:
        return "capability_a"

    def description(self) -> str:
        self.description_calls += 1
        return "Capability A."


class _CapabilityB(Capability):
    def name(self) -> str:
        return "capability_b"

    def description(self) -> str:
        return "Capability B."


def _registry(*capabilities: Capability) -> CapabilityRegistry:
    return CapabilityRegistry().register_many(list(capabilities))


def test_capability_existente():
    capability = _CapabilityA()
    manager = CapabilityManager(registry=_registry(capability))

    assert manager.capability("capability_a") is capability


def test_capability_inexistente_retorna_none():
    manager = CapabilityManager(registry=_registry(_CapabilityA()))

    assert manager.capability("does_not_exist") is None


def test_exists():
    manager = CapabilityManager(registry=_registry(_CapabilityA()))

    assert manager.exists("capability_a") is True
    assert manager.exists("does_not_exist") is False


def test_capabilities():
    capability_a = _CapabilityA()
    capability_b = _CapabilityB()
    manager = CapabilityManager(registry=_registry(capability_a, capability_b))

    assert manager.capabilities() == [capability_a, capability_b]


def test_lista_vazia():
    manager = CapabilityManager(registry=CapabilityRegistry())

    assert manager.capabilities() == []


def test_retorno_preservado():
    capability = _CapabilityA()
    manager = CapabilityManager(registry=_registry(capability))

    assert manager.capability("capability_a") is capability
    assert manager.capabilities()[0] is capability


def test_nenhuma_execucao_de_capability():
    capability = _CapabilityA()
    manager = CapabilityManager(registry=_registry(capability))

    manager.capability("capability_a")
    manager.exists("capability_a")
    manager.capabilities()

    assert capability.description_calls == 0


def test_imutabilidade_rejects_attribute_assignment():
    manager = CapabilityManager(registry=_registry(_CapabilityA()))

    with pytest.raises(ValidationError):
        manager.registry = CapabilityRegistry()


def test_injecao_uses_exactly_the_registry_provided():
    registry = _registry(_CapabilityA())

    manager = CapabilityManager(registry=registry)

    assert manager.registry is registry


def test_conhece_exclusivamente_capability_registry():
    source = inspect.getsource(capability_manager)

    assert "CapabilityRegistry" in source
    assert "Capability" in source


def test_ausencia_de_runtime():
    source = inspect.getsource(capability_manager)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(capability_manager)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(capability_manager)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(capability_manager)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(capability_manager)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(capability_manager)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(capability_manager)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(capability_manager)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_capability_manager():
    manager = build_default_capability_manager()

    assert isinstance(manager, CapabilityManager)


def test_factory_usa_exclusivamente_build_default_capability_registry():
    source = inspect.getsource(capability_manager_factory)

    assert "build_default_capability_registry" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = capability_manager_factory.build_default_capability_registry

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        capability_manager_factory, "build_default_capability_registry", _spy
    )

    build_default_capability_manager()

    assert calls["count"] == 1
