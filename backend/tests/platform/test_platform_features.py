import inspect

import pytest
from pydantic import ValidationError

from app.platform.features import platform_features, platform_features_factory
from app.platform.features.feature import Feature
from app.platform.features.feature_executor import FeatureExecutor
from app.platform.features.feature_manager import FeatureManager
from app.platform.features.feature_registry import FeatureRegistry
from app.platform.features.platform_features import PlatformFeatures
from app.platform.features.platform_features_factory import build_default_platform_features


class _Feature(Feature):
    def __init__(self, label: str, is_enabled: bool) -> None:
        self.label = label
        self._enabled = is_enabled

    def name(self) -> str:
        return self.label

    def enabled(self) -> bool:
        return self._enabled


def _platform_features(*features: Feature) -> PlatformFeatures:
    registry = FeatureRegistry().register_many(list(features))
    manager = FeatureManager(registry=registry)
    executor = FeatureExecutor(manager=manager)
    return PlatformFeatures(executor=executor)


def test_features_retorna_exatamente_executor_execute():
    features = _platform_features(_Feature("a", True), _Feature("b", False))

    assert features.features() == (True, False)


def test_identidade_preservada(monkeypatch):
    sentinel = (True, False)

    def _fake_execute(self):
        return sentinel

    monkeypatch.setattr(FeatureExecutor, "execute", _fake_execute)

    features = _platform_features()

    assert features.features() is sentinel


def test_execute_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = FeatureExecutor.execute

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(FeatureExecutor, "execute", _spy)

    features = _platform_features(_Feature("a", True))
    features.features()

    assert calls["count"] == 1


def test_ausencia_de_reconstrucao(monkeypatch):
    calls = {"count": 0}
    original = FeatureExecutor.execute

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(FeatureExecutor, "execute", _spy)

    features = _platform_features(_Feature("a", True))
    features.features()
    features.features()

    assert calls["count"] == 2


def test_imutabilidade_rejects_attribute_assignment():
    features = _platform_features()

    with pytest.raises(ValidationError):
        features.executor = FeatureExecutor(
            manager=FeatureManager(registry=FeatureRegistry())
        )


def test_injecao_uses_exactly_the_executor_provided():
    executor = FeatureExecutor(manager=FeatureManager(registry=FeatureRegistry()))

    features = PlatformFeatures(executor=executor)

    assert features.executor is executor


def test_conhece_exclusivamente_feature_executor():
    source = inspect.getsource(platform_features)

    assert "FeatureExecutor" in source
    assert "FeatureManager" not in source
    assert "FeatureRegistry" not in source
    assert "Feature(" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(platform_features)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(platform_features)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(platform_features)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(platform_features)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(platform_features)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_capabilities():
    source = inspect.getsource(platform_features)
    assert "app.platform.capabilities" not in source
    assert "Capability" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(platform_features)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(platform_features)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(platform_features)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_platform_features():
    features = build_default_platform_features()

    assert isinstance(features, PlatformFeatures)


def test_factory_usa_exclusivamente_build_default_feature_executor():
    source = inspect.getsource(platform_features_factory)

    assert "build_default_feature_executor" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.platform.capabilities" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_executor_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = platform_features_factory.build_default_feature_executor

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_features_factory, "build_default_feature_executor", _spy
    )

    build_default_platform_features()

    assert calls["count"] == 1
