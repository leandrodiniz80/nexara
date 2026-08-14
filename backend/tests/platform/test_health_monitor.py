import inspect

from app.platform.health import health_monitor, health_monitor_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager import HealthManager
from app.platform.health.health_monitor import HealthMonitor
from app.platform.health.health_monitor_factory import build_default_health_monitor
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


def _monitor(*checks: HealthCheck) -> HealthMonitor:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = HealthManager(registry=registry)
    executor = HealthExecutor(manager=manager)
    service = HealthReportService(executor=executor)
    health = PlatformHealth(health_report_service=service)
    return HealthMonitor(platform_health=health)


def test_monitor_retorna_exatamente_o_health_report():
    monitor = _monitor(_Check("a", True), _Check("b", False))

    report = monitor.monitor()

    assert isinstance(report, HealthReport)
    assert report.results == (True, False)
    assert report.healthy is False


def test_platform_health_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformHealth.health

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformHealth, "health", _spy)

    monitor = _monitor(_Check("a", True))
    monitor.monitor()

    assert calls["count"] == 1


def test_retorno_preserva_identidade(monkeypatch):
    sentinel = HealthReport(results=(True,), healthy=True)

    def _fake_health(self):
        return sentinel

    monkeypatch.setattr(PlatformHealth, "health", _fake_health)

    monitor = _monitor()

    assert monitor.monitor() is sentinel


def test_factory_retorna_health_monitor():
    monitor = build_default_health_monitor()

    assert isinstance(monitor, HealthMonitor)


def test_factory_usa_exclusivamente_build_default_platform_health():
    source = inspect.getsource(health_monitor_factory)

    assert "build_default_platform_health" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_platform_health_da_factory_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = health_monitor_factory.build_default_platform_health

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(health_monitor_factory, "build_default_platform_health", _spy)

    build_default_health_monitor()

    assert calls["count"] == 1


def test_conhece_exclusivamente_platform_health():
    source = inspect.getsource(health_monitor)

    assert "PlatformHealth" in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(health_monitor)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_platform_bootstrap():
    source = inspect.getsource(health_monitor)
    assert "PlatformBootstrap" not in source


def test_nenhuma_referencia_a_platform_kernel_facade():
    source = inspect.getsource(health_monitor)
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(health_monitor)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(health_monitor)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(health_monitor)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(health_monitor)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(health_monitor)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(health_monitor)
    assert "app.automation" not in source


def test_nenhum_scheduler_polling_worker_dashboard_api_ou_cache():
    source = inspect.getsource(health_monitor)
    assert "Scheduler" not in source
    assert "Polling" not in source
    assert "poll" not in source.lower()
    assert "Worker" not in source
    assert "Dashboard" not in source
    assert "api" not in source.lower()
    assert "cache" not in source.lower()
