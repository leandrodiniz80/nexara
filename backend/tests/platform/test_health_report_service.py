import inspect

from app.platform.health import health_report_service, health_report_service_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager import HealthManager
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_service import HealthReportService
from app.platform.health.health_report_service_factory import (
    build_default_health_report_service,
)


class _Check(HealthCheck):
    def __init__(self, label: str, result: bool) -> None:
        self.label = label
        self.result = result

    def name(self) -> str:
        return self.label

    def check(self) -> bool:
        return self.result


def _service(*checks: HealthCheck) -> HealthReportService:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = HealthManager(registry=registry)
    executor = HealthExecutor(manager=manager)
    return HealthReportService(executor=executor)


def test_lista_vazia():
    service = _service()

    report = service.build()

    assert report.results == ()
    assert report.healthy is True


def test_um_resultado():
    service = _service(_Check("a", True))

    report = service.build()

    assert report.results == (True,)
    assert report.healthy is True


def test_varios_resultados():
    service = _service(_Check("a", True), _Check("b", False), _Check("c", True))

    report = service.build()

    assert report.results == (True, False, True)
    assert report.healthy is False


def test_retorno_e_exatamente_health_report():
    service = _service(_Check("a", True))

    report = service.build()

    assert isinstance(report, HealthReport)


def test_executor_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = HealthExecutor.run

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(HealthExecutor, "run", _spy)

    service = _service(_Check("a", True))
    service.build()

    assert calls["count"] == 1


def test_build_health_report_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = health_report_service.build_health_report

    def _spy(results):
        calls["count"] += 1
        return original(results)

    monkeypatch.setattr(health_report_service, "build_health_report", _spy)

    service = _service(_Check("a", True))
    service.build()

    assert calls["count"] == 1


def test_factory_retorna_health_report_service():
    service = build_default_health_report_service()

    assert isinstance(service, HealthReportService)


def test_factory_usa_exclusivamente_build_default_health_executor():
    source = inspect.getsource(health_report_service_factory)

    assert "build_default_health_executor" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_executor_da_factory_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = health_report_service_factory.build_default_health_executor

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        health_report_service_factory, "build_default_health_executor", _spy
    )

    build_default_health_report_service()

    assert calls["count"] == 1


def test_conhece_exclusivamente_health_executor():
    source = inspect.getsource(health_report_service)

    assert "HealthExecutor" in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source
    assert "PlatformContainer" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(health_report_service)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_report_service)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_report_service)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_report_service)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_report_service)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(health_report_service)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(health_report_service)
    assert "app.automation" not in source


def test_nenhum_cache_ou_integracao():
    source = inspect.getsource(health_report_service)
    assert "cache" not in source.lower()
