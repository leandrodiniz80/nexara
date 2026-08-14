import inspect

import pytest
from pydantic import ValidationError

from app.platform.features import feature_executor, feature_executor_factory
from app.platform.features.feature import Feature
from app.platform.features.feature_executor import FeatureExecutor
from app.platform.features.feature_executor_factory import build_default_feature_executor
from app.platform.features.feature_manager import FeatureManager
from app.platform.features.feature_registry import FeatureRegistry


class _Feature(Feature):
    def __init__(self, label: str, is_enabled: bool) -> None:
        self.label = label
        self._enabled = is_enabled
        self.enabled_calls = 0

    def name(self) -> str:
        return self.label

    def enabled(self) -> bool:
        self.enabled_calls += 1
        return self._enabled


def _executor(*features: Feature) -> FeatureExecutor:
    registry = FeatureRegistry().register_many(list(features))
    manager = FeatureManager(registry=registry)
    return FeatureExecutor(manager=manager)


def test_lista_vazia():
    executor = _executor()

    assert executor.execute() == ()


def test_uma_feature():
    feature = _Feature("a", True)
    executor = _executor(feature)

    result = executor.execute()

    assert result == (True,)
    assert feature.enabled_calls == 1


def test_varias_features():
    feature_a = _Feature("a", True)
    feature_b = _Feature("b", False)
    feature_c = _Feature("c", True)
    executor = _executor(feature_a, feature_b, feature_c)

    result = executor.execute()

    assert result == (True, False, True)
    assert feature_a.enabled_calls == 1
    assert feature_b.enabled_calls == 1
    assert feature_c.enabled_calls == 1


def test_ordem_preservada():
    feature_a = _Feature("a", True)
    feature_b = _Feature("b", False)
    executor = _executor(feature_a, feature_b)

    result = executor.execute()

    assert result == (True, False)


def test_enabled_chamado_exatamente_uma_vez_por_feature():
    feature = _Feature("a", True)
    executor = _executor(feature)

    executor.execute()

    assert feature.enabled_calls == 1


def test_retorno_preserva_exatamente_a_ordem():
    feature_a = _Feature("a", False)
    feature_b = _Feature("b", True)
    feature_c = _Feature("c", False)
    executor = _executor(feature_a, feature_b, feature_c)

    result = executor.execute()

    assert list(result) == [False, True, False]


def test_identidade_preservada():
    feature = _Feature("a", True)
    executor = _executor(feature)

    result = executor.execute()

    assert result[0] is True


def test_imutabilidade_rejects_attribute_assignment():
    executor = _executor(_Feature("a", True))

    with pytest.raises(ValidationError):
        executor.manager = FeatureManager(registry=FeatureRegistry())


def test_injecao_uses_exactly_the_manager_provided():
    manager = FeatureManager(registry=FeatureRegistry().register(_Feature("a", True)))

    executor = FeatureExecutor(manager=manager)

    assert executor.manager is manager


def test_conhece_exclusivamente_feature_manager():
    source = inspect.getsource(feature_executor)

    assert "FeatureManager" in source
    assert "FeatureRegistry" not in source


def test_ausencia_de_runtime():
    source = inspect.getsource(feature_executor)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(feature_executor)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(feature_executor)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(feature_executor)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(feature_executor)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_capabilities():
    source = inspect.getsource(feature_executor)
    assert "app.platform.capabilities" not in source
    assert "Capability" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(feature_executor)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(feature_executor)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(feature_executor)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source


def test_factory_retorna_feature_executor():
    executor = build_default_feature_executor()

    assert isinstance(executor, FeatureExecutor)


def test_factory_usa_exclusivamente_build_default_feature_manager():
    source = inspect.getsource(feature_executor_factory)

    assert "build_default_feature_manager" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.platform.lifecycle" not in source
    assert "app.platform.health" not in source
    assert "app.platform.events" not in source
    assert "app.platform.capabilities" not in source
    assert "app.observability" not in source
    assert "app.application.command_bus" not in source
    assert "app.application.query_bus" not in source


def test_manager_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = feature_executor_factory.build_default_feature_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(feature_executor_factory, "build_default_feature_manager", _spy)

    build_default_feature_executor()

    assert calls["count"] == 1
