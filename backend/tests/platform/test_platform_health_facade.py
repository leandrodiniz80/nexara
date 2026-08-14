import inspect

from app.platform.health import platform_health_facade, platform_health_facade_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_coordinator import HealthCoordinator
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager import HealthManager
from app.platform.health.health_monitor import HealthMonitor
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_service import HealthReportService
from app.platform.health.platform_health import PlatformHealth
from app.platform.health.platform_health_facade import PlatformHealthFacade
from app.platform.health.platform_health_facade_factory import (
    build_default_platform_health_facade,
)


class _Check(HealthCheck):
    def __init__(self, label: str, result: bool) -> None:
        self.label = label
        self.result = result

    def name(self) -> str:
        return self.label

    def check(self) -> bool:
        return self.result


def _facade(*checks: HealthCheck) -> PlatformHealthFacade:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = HealthManager(registry=registry)
    executor = HealthExecutor(manager=manager)
    service = HealthReportService(executor=executor)
    health = PlatformHealth(health_report_service=service)
    monitor = HealthMonitor(platform_health=health)
    coordinator = HealthCoordinator(health_monitor=monitor)
    return PlatformHealthFacade(health_coordinator=coordinator)


def test_health_retorna_exatamente_o_health_report():
    facade = _facade(_Check("a", True), _Check("b", False))

    report = facade.health()

    assert isinstance(report, HealthReport)
    assert report.results == (True, False)
    assert report.healthy is False


def test_health_coordinator_coordinate_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = HealthCoordinator.coordinate

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(HealthCoordinator, "coordinate", _spy)

    facade = _facade(_Check("a", True))
    facade.health()

    assert calls["count"] == 1


def test_retorno_preserva_identidade(monkeypatch):
    sentinel = HealthReport(results=(True,), healthy=True)

    def _fake_coordinate(self):
        return sentinel

    monkeypatch.setattr(HealthCoordinator, "coordinate", _fake_coordinate)

    facade = _facade()

    assert facade.health() is sentinel


def test_factory_retorna_platform_health_facade():
    facade = build_default_platform_health_facade()

    assert isinstance(facade, PlatformHealthFacade)


def test_factory_usa_exclusivamente_build_default_health_coordinator():
    source = inspect.getsource(platform_health_facade_factory)

    assert "build_default_health_coordinator" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_health_coordinator_da_factory_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = platform_health_facade_factory.build_default_health_coordinator

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_health_facade_factory, "build_default_health_coordinator", _spy
    )

    build_default_platform_health_facade()

    assert calls["count"] == 1


def test_conhece_exclusivamente_health_coordinator():
    source = inspect.getsource(platform_health_facade)

    assert "HealthCoordinator" in source
    assert "HealthMonitor" not in source
    assert "PlatformHealth" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(platform_health_facade)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_platform_bootstrap():
    source = inspect.getsource(platform_health_facade)
    assert "PlatformBootstrap" not in source


def test_nenhuma_referencia_a_platform_kernel_facade():
    source = inspect.getsource(platform_health_facade)
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(platform_health_facade)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(platform_health_facade)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(platform_health_facade)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(platform_health_facade)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(platform_health_facade)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(platform_health_facade)
    assert "app.automation" not in source


def test_nenhum_dashboard_api_cache_scheduler_ou_worker():
    source = inspect.getsource(platform_health_facade)
    assert "Dashboard" not in source
    assert "api" not in source.lower()
    assert "cache" not in source.lower()
    assert "Scheduler" not in source
    assert "Worker" not in source
