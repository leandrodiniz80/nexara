import inspect

from app.platform.health import platform_health, platform_health_factory
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager import HealthManager
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_service import HealthReportService
from app.platform.health.platform_health import PlatformHealth
from app.platform.health.platform_health_factory import build_default_platform_health


class _Check(HealthCheck):
    def __init__(self, label: str, result: bool) -> None:
        self.label = label
        self.result = result

    def name(self) -> str:
        return self.label

    def check(self) -> bool:
        return self.result


def _health(*checks: HealthCheck) -> PlatformHealth:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = HealthManager(registry=registry)
    executor = HealthExecutor(manager=manager)
    service = HealthReportService(executor=executor)
    return PlatformHealth(health_report_service=service)


def test_health_retorna_exatamente_o_health_report():
    platform_health_obj = _health(_Check("a", True), _Check("b", False))

    report = platform_health_obj.health()

    assert isinstance(report, HealthReport)
    assert report.results == (True, False)
    assert report.healthy is False


def test_health_report_service_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = HealthReportService.build

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(HealthReportService, "build", _spy)

    platform_health_obj = _health(_Check("a", True))
    platform_health_obj.health()

    assert calls["count"] == 1


def test_retorno_preserva_identidade(monkeypatch):
    sentinel = HealthReport(results=(True,), healthy=True)

    def _fake_build(self):
        return sentinel

    monkeypatch.setattr(HealthReportService, "build", _fake_build)

    platform_health_obj = _health()

    assert platform_health_obj.health() is sentinel


def test_factory_retorna_platform_health():
    platform_health_obj = build_default_platform_health()

    assert isinstance(platform_health_obj, PlatformHealth)


def test_factory_usa_exclusivamente_build_default_health_report_service():
    source = inspect.getsource(platform_health_factory)

    assert "build_default_health_report_service" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_health_report_service_da_factory_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = platform_health_factory.build_default_health_report_service

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_health_factory, "build_default_health_report_service", _spy
    )

    build_default_platform_health()

    assert calls["count"] == 1


def test_conhece_exclusivamente_health_report_service():
    source = inspect.getsource(platform_health)

    assert "HealthReportService" in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source
    assert "PlatformContainer" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(platform_health)
    assert "PlatformLifecycle" not in source
    assert "Lifecycle" not in source


def test_nenhuma_referencia_a_platform_bootstrap():
    source = inspect.getsource(platform_health)
    assert "PlatformBootstrap" not in source


def test_nenhuma_referencia_a_platform_kernel_facade():
    source = inspect.getsource(platform_health)
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(platform_health)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(platform_health)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(platform_health)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(platform_health)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(platform_health)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(platform_health)
    assert "app.automation" not in source


def test_nenhum_health_status_dashboard_ou_api():
    source = inspect.getsource(platform_health)
    assert "HealthStatus" not in source
    assert "Dashboard" not in source
    assert "api" not in source.lower()


def test_nenhum_cache():
    source = inspect.getsource(platform_health)
    assert "cache" not in source.lower()
