import inspect

import pytest
from pydantic import ValidationError

from app.platform.features import feature_registry
from app.platform.features.feature import Feature
from app.platform.features.feature_registry import FeatureRegistry
from app.platform.features.feature_registry_factory import build_default_feature_registry


class _FeatureA(Feature):
    def name(self) -> str:
        return "feature_a"

    def enabled(self) -> bool:
        return True


class _FeatureB(Feature):
    def name(self) -> str:
        return "feature_b"

    def enabled(self) -> bool:
        return False


class _FeatureC(Feature):
    def name(self) -> str:
        return "feature_c"

    def enabled(self) -> bool:
        return True


def test_feature_e_abstrata():
    with pytest.raises(TypeError):
        Feature()


def test_registry_vazio_por_padrao():
    registry = FeatureRegistry()

    assert registry.list() == []


def test_registro_adds_the_given_feature():
    feature = _FeatureA()
    registry = FeatureRegistry()

    updated = registry.register(feature)

    assert updated.list() == [feature]
    assert registry.list() == []


def test_register_many_adds_every_given_feature_in_order():
    feature_a = _FeatureA()
    feature_b = _FeatureB()
    registry = FeatureRegistry()

    updated = registry.register_many([feature_a, feature_b])

    assert updated.list() == [feature_a, feature_b]


def test_find_existente_returns_the_matching_feature():
    feature = _FeatureA()
    registry = FeatureRegistry().register(feature)

    assert registry.find("feature_a") is feature


def test_find_inexistente_returns_none():
    registry = FeatureRegistry().register(_FeatureA())

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = FeatureRegistry().register(_FeatureA())

    assert registry.exists("feature_a") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = FeatureRegistry()
    registry = registry.register(_FeatureA())
    registry = registry.register(_FeatureB())
    registry = registry.register(_FeatureC())

    assert [f.name() for f in registry.list()] == ["feature_a", "feature_b", "feature_c"]


def test_register_never_mutates_the_previous_registry():
    original = FeatureRegistry()

    updated = original.register(_FeatureA())

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_imutabilidade_rejects_attribute_assignment():
    registry = FeatureRegistry().register(_FeatureA())

    with pytest.raises(ValidationError):
        registry.features = ()


def test_registry_usa_exclusivamente_registry_t():
    source = inspect.getsource(feature_registry)

    assert "from app.shared.registry.registry import Registry" in source
    assert "for feature in" not in source
    assert "for item in" not in source


def test_build_default_feature_registry_e_vazio():
    registry = build_default_feature_registry()

    assert isinstance(registry, FeatureRegistry)
    assert registry.list() == []


def test_ausencia_de_runtime():
    source = inspect.getsource(feature_registry)
    assert "app.runtime" not in source


def test_ausencia_de_operations():
    source = inspect.getsource(feature_registry)
    assert "app.operations" not in source


def test_ausencia_de_lifecycle():
    source = inspect.getsource(feature_registry)
    assert "app.platform.lifecycle" not in source
    assert "Lifecycle" not in source


def test_ausencia_de_health():
    source = inspect.getsource(feature_registry)
    assert "app.platform.health" not in source
    assert "Health" not in source


def test_ausencia_de_events():
    source = inspect.getsource(feature_registry)
    assert "app.platform.events" not in source
    assert "PlatformEvent" not in source


def test_ausencia_de_capabilities():
    source = inspect.getsource(feature_registry)
    assert "app.platform.capabilities" not in source
    assert "Capability" not in source


def test_ausencia_de_observability():
    source = inspect.getsource(feature_registry)
    assert "app.observability" not in source


def test_ausencia_de_command_bus():
    source = inspect.getsource(feature_registry)
    assert "app.application.command_bus" not in source
    assert "CommandBus" not in source


def test_ausencia_de_query_bus():
    source = inspect.getsource(feature_registry)
    assert "app.application.query_bus" not in source
    assert "QueryBus" not in source
