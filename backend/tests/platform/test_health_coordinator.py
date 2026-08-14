import inspect

from app.platform.health import health_coordinator, health_coordinator_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_coordinator import HealthCoordinator
from app.platform.health.health_coordinator_factory import build_default_health_coordinator
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager import HealthManager
from app.platform.health.health_monitor import HealthMonitor
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_service import HealthReportService
from app.platform.health.platform_health import PlatformHealth


class _Check(HealthCheck):
    def __init__(self, label: str, result: bool) -> None:
        self.label = label
        self.result = result

    def name(self) -> str:
        return self.label

    def check(self) -> bool:
        return self.result


def _coordinator(*checks: HealthCheck) -> HealthCoordinator:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = HealthManager(registry=registry)
    executor = HealthExecutor(manager=manager)
    service = HealthReportService(executor=executor)
    health = PlatformHealth(health_report_service=service)
    monitor = HealthMonitor(platform_health=health)
    return HealthCoordinator(health_monitor=monitor)


def test_coordinate_retorna_exatamente_o_health_report():
    coordinator = _coordinator(_Check("a", True), _Check("b", False))

    report = coordinator.coordinate()

    assert isinstance(report, HealthReport)
    assert report.results == (True, False)
    assert report.healthy is False


def test_health_monitor_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = HealthMonitor.monitor

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(HealthMonitor, "monitor", _spy)

    coordinator = _coordinator(_Check("a", True))
    coordinator.coordinate()

    assert calls["count"] == 1


def test_retorno_preserva_identidade(monkeypatch):
    sentinel = HealthReport(results=(True,), healthy=True)

    def _fake_monitor(self):
        return sentinel

    monkeypatch.setattr(HealthMonitor, "monitor", _fake_monitor)

    coordinator = _coordinator()

    assert coordinator.coordinate() is sentinel


def test_factory_retorna_health_coordinator():
    coordinator = build_default_health_coordinator()

    assert isinstance(coordinator, HealthCoordinator)


def test_factory_usa_exclusivamente_build_default_health_monitor():
    source = inspect.getsource(health_coordinator_factory)

    assert "build_default_health_monitor" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_health_monitor_da_factory_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = health_coordinator_factory.build_default_health_monitor

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(health_coordinator_factory, "build_default_health_monitor", _spy)

    build_default_health_coordinator()

    assert calls["count"] == 1


def test_conhece_exclusivamente_health_monitor():
    source = inspect.getsource(health_coordinator)

    assert "HealthMonitor" in source
    assert "PlatformHealth" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(health_coordinator)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_platform_bootstrap():
    source = inspect.getsource(health_coordinator)
    assert "PlatformBootstrap" not in source


def test_nenhuma_referencia_a_platform_kernel_facade():
    source = inspect.getsource(health_coordinator)
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_coordinator)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_coordinator)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_coordinator)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_coordinator)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(health_coordinator)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(health_coordinator)
    assert "app.automation" not in source


def test_nenhum_scheduler_polling_worker_dashboard_api_ou_cache():
    source = inspect.getsource(health_coordinator)
    assert "Scheduler" not in source
    assert "Polling" not in source
    assert "poll" not in source.lower()
    assert "Worker" not in source
    assert "Dashboard" not in source
    assert "api" not in source.lower()
    assert "cache" not in source.lower()
