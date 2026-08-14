import inspect

from app.platform.health import health_executor, health_executor_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_executor_factory import build_default_health_executor
from app.platform.health.health_manager import HealthManager


class _Check(HealthCheck):
    def __init__(self, label: str, result: bool) -> None:
        self.label = label
        self.result = result
        self.check_calls = 0

    def name(self) -> str:
        return self.label

    def check(self) -> bool:
        self.check_calls += 1
        return self.result


def _executor(*checks: HealthCheck) -> HealthExecutor:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = HealthManager(registry=registry)
    return HealthExecutor(manager=manager)


def test_lista_vazia():
    executor = _executor()

    assert executor.run() == ()


def test_um_health_check():
    check = _Check("a", True)
    executor = _executor(check)

    result = executor.run()

    assert result == (True,)
    assert check.check_calls == 1


def test_varios_health_checks():
    check_a = _Check("a", True)
    check_b = _Check("b", False)
    check_c = _Check("c", True)
    executor = _executor(check_a, check_b, check_c)

    result = executor.run()

    assert result == (True, False, True)
    assert check_a.check_calls == 1
    assert check_b.check_calls == 1
    assert check_c.check_calls == 1


def test_ordem_preservada():
    check_a = _Check("a", True)
    check_b = _Check("b", False)
    executor = _executor(check_a, check_b)

    result = executor.run()

    assert result == (True, False)


def test_check_chamado_exatamente_uma_vez():
    check = _Check("a", True)
    executor = _executor(check)

    executor.run()

    assert check.check_calls == 1


def test_retorno_preserva_exatamente_a_ordem_dos_resultados():
    check_a = _Check("a", False)
    check_b = _Check("b", True)
    check_c = _Check("c", False)
    executor = _executor(check_a, check_b, check_c)

    result = executor.run()

    assert list(result) == [check_a.result, check_b.result, check_c.result]


def test_factory_retorna_health_executor():
    executor = build_default_health_executor()

    assert isinstance(executor, HealthExecutor)


def test_factory_usa_exclusivamente_build_default_health_manager():
    source = inspect.getsource(health_executor_factory)

    assert "build_default_health_manager" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_manager_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = health_executor_factory.build_default_health_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(health_executor_factory, "build_default_health_manager", _spy)

    build_default_health_executor()

    assert calls["count"] == 1


def test_conhece_exclusivamente_health_manager():
    source = inspect.getsource(health_executor)

    assert "HealthManager" in source
    assert "HealthCheckRegistry" not in source
    assert "PlatformContainer" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(health_executor)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_executor)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_executor)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_executor)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_executor)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(health_executor)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(health_executor)
    assert "app.automation" not in source


def test_nenhum_relatorio_status_agregado_ou_health_service():
    source = inspect.getsource(health_executor)
    assert "report" not in source.lower()
    assert "status" not in source.lower()
    assert "HealthService" not in source
