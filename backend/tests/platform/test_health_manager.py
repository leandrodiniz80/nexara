import inspect

import pytest
from pydantic import ValidationError

from app.platform.health import health_manager, health_manager_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_manager import HealthManager
from app.platform.health.health_manager_factory import build_default_health_manager


class _CheckA(HealthCheck):
    def __init__(self) -> None:
        self.check_calls = 0

    def name(self) -> str:
        return "check_a"

    def check(self) -> bool:
        self.check_calls += 1
        return True


class _CheckB(HealthCheck):
    def name(self) -> str:
        return "check_b"

    def check(self) -> bool:
        return True


def _registry(*checks: HealthCheck) -> HealthCheckRegistry:
    return HealthCheckRegistry().register_many(list(checks))


def test_check_existente():
    check = _CheckA()
    manager = HealthManager(registry=_registry(check))

    assert manager.check("check_a") is check


def test_check_inexistente_retorna_none():
    manager = HealthManager(registry=_registry(_CheckA()))

    assert manager.check("does_not_exist") is None


def test_exists():
    manager = HealthManager(registry=_registry(_CheckA()))

    assert manager.exists("check_a") is True
    assert manager.exists("does_not_exist") is False


def test_checks():
    check_a = _CheckA()
    check_b = _CheckB()
    manager = HealthManager(registry=_registry(check_a, check_b))

    assert manager.checks() == [check_a, check_b]


def test_retorno_preservado():
    check = _CheckA()
    manager = HealthManager(registry=_registry(check))

    assert manager.check("check_a") is check
    assert manager.checks()[0] is check


def test_check_nunca_executa_o_healthcheck():
    check = _CheckA()
    manager = HealthManager(registry=_registry(check))

    manager.check("check_a")
    manager.exists("check_a")
    manager.checks()

    assert check.check_calls == 0


def test_singleton_nao_e_responsabilidade_desta_classe():
    manager = HealthManager(registry=_registry(_CheckA()))

    assert manager.checks() is not manager.checks()


def test_imutabilidade_rejects_attribute_assignment():
    manager = HealthManager(registry=_registry(_CheckA()))

    with pytest.raises(ValidationError):
        manager.registry = HealthCheckRegistry()


def test_injecao_uses_exactly_the_registry_provided():
    registry = _registry(_CheckA())

    manager = HealthManager(registry=registry)

    assert manager.registry is registry


def test_conhece_exclusivamente_health_check_registry():
    source = inspect.getsource(health_manager)

    assert "HealthCheckRegistry" in source
    assert "HealthCheck" in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(health_manager)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_manager)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_manager)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_manager)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_manager)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(health_manager)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(health_manager)
    assert "app.automation" not in source


def test_nenhum_executor_status_ou_relatorio():
    source = inspect.getsource(health_manager)
    assert "executor" not in source.lower()
    assert "status" not in source.lower()
    assert "report" not in source.lower()


def test_factory_retorna_health_manager():
    manager = build_default_health_manager()

    assert isinstance(manager, HealthManager)


def test_factory_usa_exclusivamente_build_default_health_check_registry():
    source = inspect.getsource(health_manager_factory)

    assert "build_default_health_check_registry" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = health_manager_factory.build_default_health_check_registry

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        health_manager_factory, "build_default_health_check_registry", _spy
    )

    build_default_health_manager()

    assert calls["count"] == 1
