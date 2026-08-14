import inspect

import pytest
from pydantic import ValidationError

from app.platform.health import health_check_registry
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_check_registry_factory import build_default_health_check_registry


class _CheckA(HealthCheck):
    def name(self) -> str:
        return "check_a"

    def check(self) -> bool:
        return True


class _CheckB(HealthCheck):
    def name(self) -> str:
        return "check_b"

    def check(self) -> bool:
        return True


class _CheckC(HealthCheck):
    def name(self) -> str:
        return "check_c"

    def check(self) -> bool:
        return False


def test_health_check_e_abstrato():
    with pytest.raises(TypeError):
        HealthCheck()


def test_registry_vazio_por_padrao():
    registry = HealthCheckRegistry()

    assert registry.list() == []


def test_registro_adds_the_given_check():
    check = _CheckA()
    registry = HealthCheckRegistry()

    updated = registry.register(check)

    assert updated.list() == [check]
    assert registry.list() == []


def test_register_many_adds_every_given_check_in_order():
    check_a = _CheckA()
    check_b = _CheckB()
    registry = HealthCheckRegistry()

    updated = registry.register_many([check_a, check_b])

    assert updated.list() == [check_a, check_b]


def test_find_existente_returns_the_matching_check():
    check = _CheckA()
    registry = HealthCheckRegistry().register(check)

    assert registry.find("check_a") is check


def test_find_inexistente_returns_none():
    registry = HealthCheckRegistry().register(_CheckA())

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = HealthCheckRegistry().register(_CheckA())

    assert registry.exists("check_a") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = HealthCheckRegistry()
    registry = registry.register(_CheckA())
    registry = registry.register(_CheckB())
    registry = registry.register(_CheckC())

    assert [check.name() for check in registry.list()] == ["check_a", "check_b", "check_c"]


def test_register_never_mutates_the_previous_registry():
    original = HealthCheckRegistry()

    updated = original.register(_CheckA())

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_imutabilidade_rejects_attribute_assignment():
    registry = HealthCheckRegistry().register(_CheckA())

    with pytest.raises(ValidationError):
        registry.checks = ()


def test_registry_usa_exclusivamente_registry_t():
    source = inspect.getsource(health_check_registry)

    assert "from app.shared.registry.registry import Registry" in source
    assert "for check in" not in source
    assert "for item in" not in source


def test_build_default_health_check_registry_e_vazio():
    registry = build_default_health_check_registry()

    assert isinstance(registry, HealthCheckRegistry)
    assert registry.list() == []


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_check_registry)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_check_registry)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_check_registry)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_check_registry)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_lifecycle():
    source = inspect.getsource(health_check_registry)
    assert "Lifecycle" not in source
    assert "app.platform.lifecycle" not in source


def test_nenhuma_referencia_a_platform_bootstrap():
    source = inspect.getsource(health_check_registry)
    assert "PlatformBootstrap" not in source
    assert "app.platform.bootstrap" not in source
