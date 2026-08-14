import inspect

import pytest
from pydantic import ValidationError

from app.platform.capabilities import platform_capabilities, platform_capabilities_factory
from app.platform.capabilities.capability import Capability
from app.platform.capabilities.capability_executor import CapabilityExecutor
from app.platform.capabilities.capability_manager import CapabilityManager
from app.platform.capabilities.capability_registry import CapabilityRegistry
from app.platform.capabilities.platform_capabilities import PlatformCapabilities
from app.platform.capabilities.platform_capabilities_factory import (
    build_default_platform_capabilities,
)


class _Capability(Capability):
    def __init__(self, label: str, description: str) -> None:
        self.label = label
        self._description = description

    def name(self) -> str:
        return self.label

    def description(self) -> str:
        return self._description


def _platform_capabilities(*capabilities: Capability) -> PlatformCapabilities:
    registry = CapabilityRegistry().register_many(list(capabilities))
    manager = CapabilityManager(registry=registry)
    executor = CapabilityExecutor(manager=manager)
    return PlatformCapabilities(executor=executor)


def test_capabilities_retorna_exatamente_executor_execute():
    capabilities = _platform_capabilities(
        _Capability("a", "Description A"), _Capability("b", "Description B")
    )

    assert capabilities.capabilities() == ("Description A", "Description B")


def test_identidade_preservada(monkeypatch):
    sentinel = ("sentinel",)

    def _fake_execute(self):
        return sentinel

    monkeypatch.setattr(CapabilityExecutor, "execute", _fake_execute)

    capabilities = _platform_capabilities()

    assert capabilities.capabilities() is sentinel


def test_execute_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = CapabilityExecutor.execute

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(CapabilityExecutor, "execute", _spy)

    capabilities = _platform_capabilities(_Capability("a", "x"))
    capabilities.capabilities()

    assert calls["count"] == 1


def test_nenhuma_reconstrucao(monkeypatch):
    calls = {"count": 0}
    original = CapabilityExecutor.execute

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(CapabilityExecutor, "execute", _spy)

    capabilities = _platform_capabilities(_Capability("a", "x"))
    capabilities.capabilities()
    capabilities.capabilities()

    assert calls["count"] == 2


def test_imutabilidade_rejects_attribute_assignment():
    capabilities = _platform_capabilities()

    with pytest.raises(ValidationError):
        capabilities.executor = CapabilityExecutor(
            manager=CapabilityManager(registry=CapabilityRegistry())
        )


def test_injecao_uses_exactly_the_executor_provided():
    executor = CapabilityExecutor(
        manager=CapabilityManager(registry=CapabilityRegistry())
    )

    capabilities = PlatformCapabilities(executor=executor)

    assert capabilities.executor is executor


def test_conhece_exclusivamente_capability_executor():
    source = inspect.getsource(platform_capabilities)

    assert "CapabilityExecutor" in source
    assert "CapabilityManager" not in source
    assert "CapabilityRegistry" not in source
    assert "Capability(" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(platform_capabilities)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(platform_capabilities)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(platform_capabilities)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(platform_capabilities)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(platform_capabilities)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(platform_capabilities)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(platform_capabilities)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(platform_capabilities)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_platform_capabilities():
    capabilities = build_default_platform_capabilities()

    assert isinstance(capabilities, PlatformCapabilities)


def test_factory_usa_exclusivamente_build_default_capability_executor():
    source = inspect.getsource(platform_capabilities_factory)

    assert "build_default_capability_executor" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_executor_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = platform_capabilities_factory.build_default_capability_executor

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_capabilities_factory, "build_default_capability_executor", _spy
    )

    build_default_platform_capabilities()

    assert calls["count"] == 1
