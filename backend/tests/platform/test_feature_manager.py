import inspect

import pytest
from pydantic import ValidationError

from app.platform.features import feature_manager, feature_manager_factory
from app.platform.features.feature import Feature
from app.platform.features.feature_manager import FeatureManager
from app.platform.features.feature_manager_factory import build_default_feature_manager
from app.platform.features.feature_registry import FeatureRegistry


class _FeatureA(Feature):
    def __init__(self) -> None:
        self.enabled_calls = 0

    def name(self) -> str:
        return "feature_a"

    def enabled(self) -> bool:
        self.enabled_calls += 1
        return True


class _FeatureB(Feature):
    def name(self) -> str:
        return "feature_b"

    def enabled(self) -> bool:
        return False


def _registry(*features: Feature) -> FeatureRegistry:
    return FeatureRegistry().register_many(list(features))


def test_feature_existente():
    feature = _FeatureA()
    manager = FeatureManager(registry=_registry(feature))

    assert manager.feature("feature_a") is feature


def test_feature_inexistente_retorna_none():
    manager = FeatureManager(registry=_registry(_FeatureA()))

    assert manager.feature("does_not_exist") is None


def test_exists():
    manager = FeatureManager(registry=_registry(_FeatureA()))

    assert manager.exists("feature_a") is True
    assert manager.exists("does_not_exist") is False


def test_features():
    feature_a = _FeatureA()
    feature_b = _FeatureB()
    manager = FeatureManager(registry=_registry(feature_a, feature_b))

    assert manager.features() == [feature_a, feature_b]


def test_lista_vazia():
    manager = FeatureManager(registry=FeatureRegistry())

    assert manager.features() == []


def test_retorno_preservado():
    feature = _FeatureA()
    manager = FeatureManager(registry=_registry(feature))

    assert manager.feature("feature_a") is feature
    assert manager.features()[0] is feature


def test_nenhuma_execucao_de_feature():
    feature = _FeatureA()
    manager = FeatureManager(registry=_registry(feature))

    manager.feature("feature_a")
    manager.exists("feature_a")
    manager.features()

    assert feature.enabled_calls == 0


def test_imutabilidade_rejects_attribute_assignment():
    manager = FeatureManager(registry=_registry(_FeatureA()))

    with pytest.raises(ValidationError):
        manager.registry = FeatureRegistry()


def test_injecao_uses_exactly_the_registry_provided():
    registry = _registry(_FeatureA())

    manager = FeatureManager(registry=registry)

    assert manager.registry is registry


def test_conhece_exclusivamente_feature_registry():
    source = inspect.getsource(feature_manager)

    assert "FeatureRegistry" in source
    assert "Feature" in source


def test_ausencia_de_runtime():
    source = inspect.getsource(feature_manager)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(feature_manager)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(feature_manager)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(feature_manager)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(feature_manager)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_capabilities():
    source = inspect.getsource(feature_manager)
    assert "app.platform.capabilities" not in source
    assert "Capability" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(feature_manager)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(feature_manager)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(feature_manager)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_feature_manager():
    manager = build_default_feature_manager()

    assert isinstance(manager, FeatureManager)


def test_factory_usa_exclusivamente_build_default_feature_registry():
    source = inspect.getsource(feature_manager_factory)

    assert "build_default_feature_registry" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.platform.capabilities" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = feature_manager_factory.build_default_feature_registry

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(feature_manager_factory, "build_default_feature_registry", _spy)

    build_default_feature_manager()

    assert calls["count"] == 1
