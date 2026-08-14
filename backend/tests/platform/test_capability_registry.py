import inspect

import pytest
from pydantic import ValidationError

from app.platform.capabilities import capability_registry
from app.platform.capabilities.capability import Capability
from app.platform.capabilities.capability_registry import CapabilityRegistry
from app.platform.capabilities.capability_registry_factory import (
    build_default_capability_registry,
)


class _CapabilityA(Capability):
    def name(self) -> str:
        return "capability_a"

    def description(self) -> str:
        return "Capability A."


class _CapabilityB(Capability):
    def name(self) -> str:
        return "capability_b"

    def description(self) -> str:
        return "Capability B."


class _CapabilityC(Capability):
    def name(self) -> str:
        return "capability_c"

    def description(self) -> str:
        return "Capability C."


def test_capability_e_abstrata():
    with pytest.raises(TypeError):
        Capability()


def test_registry_vazio_por_padrao():
    registry = CapabilityRegistry()

    assert registry.list() == []


def test_registro_adds_the_given_capability():
    capability = _CapabilityA()
    registry = CapabilityRegistry()

    updated = registry.register(capability)

    assert updated.list() == [capability]
    assert registry.list() == []


def test_register_many_adds_every_given_capability_in_order():
    capability_a = _CapabilityA()
    capability_b = _CapabilityB()
    registry = CapabilityRegistry()

    updated = registry.register_many([capability_a, capability_b])

    assert updated.list() == [capability_a, capability_b]


def test_find_existente_returns_the_matching_capability():
    capability = _CapabilityA()
    registry = CapabilityRegistry().register(capability)

    assert registry.find("capability_a") is capability


def test_find_inexistente_returns_none():
    registry = CapabilityRegistry().register(_CapabilityA())

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = CapabilityRegistry().register(_CapabilityA())

    assert registry.exists("capability_a") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = CapabilityRegistry()
    registry = registry.register(_CapabilityA())
    registry = registry.register(_CapabilityB())
    registry = registry.register(_CapabilityC())

    assert [c.name() for c in registry.list()] == [
        "capability_a",
        "capability_b",
        "capability_c",
    ]


def test_register_never_mutates_the_previous_registry():
    original = CapabilityRegistry()

    updated = original.register(_CapabilityA())

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_imutabilidade_rejects_attribute_assignment():
    registry = CapabilityRegistry().register(_CapabilityA())

    with pytest.raises(ValidationError):
        registry.capabilities = ()


def test_registry_usa_exclusivamente_registry_t():
    source = inspect.getsource(capability_registry)

    assert "from app.shared.registry.registry import Registry" in source
    assert "for capability in" not in source
    assert "for item in" not in source


def test_build_default_capability_registry_e_vazio():
    registry = build_default_capability_registry()

    assert isinstance(registry, CapabilityRegistry)
    assert registry.list() == []


def test_ausencia_de_runtime():
    source = inspect.getsource(capability_registry)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(capability_registry)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(capability_registry)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(capability_registry)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(capability_registry)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(capability_registry)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(capability_registry)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(capability_registry)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source
