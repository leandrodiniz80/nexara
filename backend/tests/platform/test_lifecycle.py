import inspect

import pytest
from pydantic import ValidationError

from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.bootstrap.platform_kernel_facade import PlatformKernelFacade
from app.platform.health.health_check import HealthCheck
from app.platform.health.health_check_registry import HealthCheckRegistry
from app.platform.health.health_coordinator import HealthCoordinator
from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager import HealthManager as _HealthCheckManager
from app.platform.health.health_monitor import HealthMonitor
from app.platform.health.health_report import HealthReport
from app.platform.health.health_report_service import HealthReportService
from app.platform.health.platform_health import PlatformHealth
from app.platform.health.platform_health_facade import PlatformHealthFacade
from app.platform.lifecycle import platform_lifecycle, platform_lifecycle_factory
from app.platform.lifecycle.lifecycle_executor import LifecycleExecutor
from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry
from app.platform.lifecycle.lifecycle_starter import LifecycleStarter
from app.platform.lifecycle.lifecycle_stopper import LifecycleStopper
from app.platform.lifecycle.platform_lifecycle import PlatformLifecycle
from app.platform.lifecycle.platform_lifecycle_factory import build_default_platform_lifecycle


def _kernel() -> PlatformKernelFacade:
    return PlatformKernelFacade(container=PlatformContainer(bootstrap=PlatformBootstrap()))


def _health_coordinator(*checks: HealthCheck) -> HealthCoordinator:
    registry = HealthCheckRegistry().register_many(list(checks))
    manager = _HealthCheckManager(registry=registry)
    executor = HealthExecutor(manager=manager)
    service = HealthReportService(executor=executor)
    health = PlatformHealth(health_report_service=service)
    monitor = HealthMonitor(platform_health=health)
    return HealthCoordinator(health_monitor=monitor)


def _platform_health(*checks: HealthCheck) -> PlatformHealthFacade:
    return PlatformHealthFacade(health_coordinator=_health_coordinator(*checks))


class _Participant(LifecycleParticipant):
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


def _manager(*participants: LifecycleParticipant) -> LifecycleManager:
    registry = LifecycleParticipantRegistry().register_many(list(participants))
    return LifecycleManager(registry=registry)


def _executor(manager: LifecycleManager | None = None) -> LifecycleExecutor:
    manager = manager or _manager()
    return LifecycleExecutor(
        starter=LifecycleStarter(manager=manager), stopper=LifecycleStopper(manager=manager)
    )


def _lifecycle(
    *,
    kernel=None,
    lifecycle_manager=None,
    lifecycle_executor=None,
    health_coordinator=None,
    platform_health=None,
) -> PlatformLifecycle:
    manager = lifecycle_manager or _manager()
    return PlatformLifecycle(
        kernel=kernel or _kernel(),
        lifecycle_manager=manager,
        lifecycle_executor=lifecycle_executor or _executor(manager),
        health_coordinator=health_coordinator or _health_coordinator(),
        platform_health=platform_health or _platform_health(),
    )


def test_start_retorna_platform_kernel_facade():
    kernel = _kernel()
    lifecycle = _lifecycle(kernel=kernel)

    assert lifecycle.start() is kernel


def test_stop_retorna_true():
    lifecycle = _lifecycle()

    assert lifecycle.stop() is True


def test_restart_retorna_platform_kernel_facade():
    kernel = _kernel()
    lifecycle = _lifecycle(kernel=kernel)

    assert lifecycle.restart() is kernel


def test_restart_chama_stop_antes_de_start(monkeypatch):
    call_order: list[str] = []
    original_stop = PlatformLifecycle.stop
    original_start = PlatformLifecycle.start

    def _stop(self):
        call_order.append("stop")
        return original_stop(self)

    def _start(self):
        call_order.append("start")
        return original_start(self)

    monkeypatch.setattr(PlatformLifecycle, "stop", _stop)
    monkeypatch.setattr(PlatformLifecycle, "start", _start)

    lifecycle = _lifecycle()
    lifecycle.restart()

    assert call_order == ["stop", "start"]


def test_kernel_preservado():
    kernel = _kernel()

    lifecycle = _lifecycle(kernel=kernel)

    assert lifecycle.kernel is kernel


def test_lifecycle_manager_e_preservado():
    manager = _manager()

    lifecycle = _lifecycle(lifecycle_manager=manager)

    assert lifecycle.lifecycle_manager is manager


def test_lifecycle_executor_e_preservado():
    executor = _executor()

    lifecycle = _lifecycle(lifecycle_executor=executor)

    assert lifecycle.lifecycle_executor is executor


def test_health_coordinator_e_preservado():
    coordinator = _health_coordinator()

    lifecycle = _lifecycle(health_coordinator=coordinator)

    assert lifecycle.health_coordinator is coordinator


def test_platform_health_e_preservado():
    health = _platform_health()

    lifecycle = _lifecycle(platform_health=health)

    assert lifecycle.platform_health is health


def test_objeto_frozen():
    lifecycle = _lifecycle()

    with pytest.raises(ValidationError):
        lifecycle.kernel = _kernel()

    with pytest.raises(ValidationError):
        lifecycle.lifecycle_manager = _manager()

    with pytest.raises(ValidationError):
        lifecycle.lifecycle_executor = _executor()

    with pytest.raises(ValidationError):
        lifecycle.health_coordinator = _health_coordinator()

    with pytest.raises(ValidationError):
        lifecycle.platform_health = _platform_health()


def test_lifecycle_manager_nunca_e_chamado():
    participant = _Participant()
    manager = _manager(participant)
    lifecycle = _lifecycle(lifecycle_manager=manager)

    lifecycle.start()
    lifecycle.stop()
    lifecycle.restart()

    assert participant.start_calls == 0
    assert participant.stop_calls == 0


def test_lifecycle_manager_metodos_nunca_sao_chamados(monkeypatch):
    calls: list[str] = []
    original_participant = LifecycleManager.participant
    original_participants = LifecycleManager.participants
    original_exists = LifecycleManager.exists

    def _participant(self, name):
        calls.append("participant")
        return original_participant(self, name)

    def _participants(self):
        calls.append("participants")
        return original_participants(self)

    def _exists(self, name):
        calls.append("exists")
        return original_exists(self, name)

    monkeypatch.setattr(LifecycleManager, "participant", _participant)
    monkeypatch.setattr(LifecycleManager, "participants", _participants)
    monkeypatch.setattr(LifecycleManager, "exists", _exists)

    lifecycle = _lifecycle()
    lifecycle.start()
    lifecycle.stop()
    lifecycle.restart()

    assert calls == []


def _spy_executor_calls(monkeypatch) -> list[str]:
    calls: list[str] = []
    original_start = LifecycleExecutor.start
    original_stop = LifecycleExecutor.stop

    def _start(self):
        calls.append("start")
        return original_start(self)

    def _stop(self):
        calls.append("stop")
        return original_stop(self)

    monkeypatch.setattr(LifecycleExecutor, "start", _start)
    monkeypatch.setattr(LifecycleExecutor, "stop", _stop)
    return calls


def test_lifecycle_executor_start_chamado_exatamente_uma_vez(monkeypatch):
    calls = _spy_executor_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.start()

    assert calls == ["start"]


def test_lifecycle_executor_stop_chamado_exatamente_uma_vez(monkeypatch):
    calls = _spy_executor_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.stop()

    assert calls == ["stop"]


def test_lifecycle_executor_start_continua_chamado_exatamente_uma_vez_durante_start(
    monkeypatch,
):
    calls = _spy_executor_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.start()

    assert calls == ["start"]


def test_restart_chama_executor_stop_antes_de_executor_start(monkeypatch):
    calls = _spy_executor_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.restart()

    assert calls == ["stop", "start"]


def test_lifecycle_participant_start_e_chamado_via_executor_ao_iniciar():
    participant = _Participant()
    manager = _manager(participant)
    lifecycle = _lifecycle(lifecycle_manager=manager, lifecycle_executor=_executor(manager))

    lifecycle.start()

    assert participant.start_calls == 1
    assert participant.stop_calls == 0


def test_lifecycle_participant_stop_e_chamado_via_executor_ao_parar():
    participant = _Participant()
    manager = _manager(participant)
    lifecycle = _lifecycle(lifecycle_manager=manager, lifecycle_executor=_executor(manager))

    lifecycle.stop()

    assert participant.start_calls == 0
    assert participant.stop_calls == 1


def test_restart_provoca_um_stop_e_um_start_no_participante():
    participant = _Participant()
    manager = _manager(participant)
    lifecycle = _lifecycle(lifecycle_manager=manager, lifecycle_executor=_executor(manager))

    lifecycle.restart()

    assert participant.start_calls == 1
    assert participant.stop_calls == 1


def _spy_coordinate_calls(monkeypatch) -> list[str]:
    calls: list[str] = []
    original = HealthCoordinator.coordinate

    def _spy(self):
        calls.append("coordinate")
        return original(self)

    monkeypatch.setattr(HealthCoordinator, "coordinate", _spy)
    return calls


def test_health_coordinator_coordinate_chamado_exatamente_uma_vez_durante_start(monkeypatch):
    calls = _spy_coordinate_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.start()

    assert calls == ["coordinate"]


def test_lifecycle_executor_start_continua_chamado_exatamente_uma_vez_apos_health(
    monkeypatch,
):
    calls = _spy_executor_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.start()

    assert calls == ["start"]


def test_health_coordinator_executado_antes_de_executor_start(monkeypatch):
    call_order: list[str] = []
    original_coordinate = HealthCoordinator.coordinate
    original_executor_start = LifecycleExecutor.start

    def _coordinate(self):
        call_order.append("coordinate")
        return original_coordinate(self)

    def _executor_start(self):
        call_order.append("executor_start")
        return original_executor_start(self)

    monkeypatch.setattr(HealthCoordinator, "coordinate", _coordinate)
    monkeypatch.setattr(LifecycleExecutor, "start", _executor_start)

    lifecycle = _lifecycle()
    lifecycle.start()

    assert call_order == ["coordinate", "executor_start"]


def test_start_continua_retornando_exatamente_o_kernel_apos_health():
    kernel = _kernel()
    lifecycle = _lifecycle(kernel=kernel)

    assert lifecycle.start() is kernel


def test_stop_continua_nao_chamando_health_coordinator(monkeypatch):
    calls = _spy_coordinate_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.stop()

    assert calls == []


def test_restart_chama_executor_stop_coordinate_e_executor_start_nesta_ordem(monkeypatch):
    call_order: list[str] = []
    original_coordinate = HealthCoordinator.coordinate
    original_executor_start = LifecycleExecutor.start
    original_executor_stop = LifecycleExecutor.stop

    def _coordinate(self):
        call_order.append("coordinate")
        return original_coordinate(self)

    def _executor_start(self):
        call_order.append("executor_start")
        return original_executor_start(self)

    def _executor_stop(self):
        call_order.append("executor_stop")
        return original_executor_stop(self)

    monkeypatch.setattr(HealthCoordinator, "coordinate", _coordinate)
    monkeypatch.setattr(LifecycleExecutor, "start", _executor_start)
    monkeypatch.setattr(LifecycleExecutor, "stop", _executor_stop)

    lifecycle = _lifecycle()
    lifecycle.restart()

    assert call_order == ["executor_stop", "coordinate", "executor_start"]


def test_restart_chama_health_coordinator_coordinate_exatamente_uma_vez(monkeypatch):
    calls = _spy_coordinate_calls(monkeypatch)

    lifecycle = _lifecycle()
    lifecycle.restart()

    assert calls == ["coordinate"]


def test_health_retorna_exatamente_o_resultado_de_platform_health(monkeypatch):
    sentinel = HealthReport(results=(True,), healthy=True)

    def _fake_health(self):
        return sentinel

    monkeypatch.setattr(PlatformHealthFacade, "health", _fake_health)

    lifecycle = _lifecycle()

    assert lifecycle.health() is sentinel


def test_health_identidade_preservada(monkeypatch):
    sentinel = HealthReport(results=(), healthy=True)

    def _fake_health(self):
        return sentinel

    monkeypatch.setattr(PlatformHealthFacade, "health", _fake_health)

    lifecycle = _lifecycle()

    assert lifecycle.health() is sentinel
    assert lifecycle.health() is sentinel


def test_health_chama_platform_health_health_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = PlatformHealthFacade.health

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformHealthFacade, "health", _spy)

    lifecycle = _lifecycle()
    lifecycle.health()

    assert calls["count"] == 1


def test_health_sem_cache_chama_platform_health_a_cada_chamada(monkeypatch):
    calls = {"count": 0}
    original = PlatformHealthFacade.health

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(PlatformHealthFacade, "health", _spy)

    lifecycle = _lifecycle()
    lifecycle.health()
    lifecycle.health()

    assert calls["count"] == 2


def test_lifecycle_conhece_platform_kernel_facade_lifecycle_manager_executor_e_health():
    source = inspect.getsource(platform_lifecycle)

    assert "PlatformKernelFacade" in source
    assert "LifecycleManager" in source
    assert "LifecycleExecutor" in source
    assert "HealthCoordinator" in source
    assert "PlatformHealthFacade" in source
    assert "PlatformContainer" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformServiceResolver" not in source
    assert "PlatformServiceRegistry" not in source
    assert "LifecycleParticipant" not in source
    assert "LifecycleStarter" not in source
    assert "LifecycleStopper" not in source
    assert "HealthMonitor" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source


def test_lifecycle_nenhuma_factory_alem_da_propria():
    source = inspect.getsource(platform_lifecycle)

    assert "build_default" not in source


def test_lifecycle_nenhuma_referencia_a_runtime():
    source = inspect.getsource(platform_lifecycle)
    assert "app.runtime" not in source


def test_lifecycle_nenhuma_referencia_a_operations():
    source = inspect.getsource(platform_lifecycle)
    assert "app.operations" not in source


def test_lifecycle_nenhuma_referencia_a_crm():
    source = inspect.getsource(platform_lifecycle)
    assert "app.crm" not in source


def test_lifecycle_nenhuma_referencia_a_workflow():
    source = inspect.getsource(platform_lifecycle)
    assert "app.workflows" not in source


def test_lifecycle_nenhuma_referencia_a_decision():
    source = inspect.getsource(platform_lifecycle)
    assert "app.decision" not in source


def test_lifecycle_nenhuma_referencia_a_automation():
    source = inspect.getsource(platform_lifecycle)
    assert "app.automation" not in source


def test_lifecycle_nenhum_service_concreto():
    source = inspect.getsource(platform_lifecycle)

    assert "CommandBusService" not in source
    assert "QueryBusService" not in source
    assert "PublicUseCaseService" not in source
    assert "PresentationFacade" not in source
    assert "PlatformInterface" not in source
    assert "PlatformExecutionOrchestrator" not in source


def test_lifecycle_nenhuma_instanciacao_direta():
    source = inspect.getsource(platform_lifecycle)

    forbidden_instantiations = [
        "RuntimeEngine(",
        "OperationsCoordinator(",
        "CommandBus(",
        "QueryBus(",
        "ExecutionPipeline(",
        "PlatformExecutionOrchestrator(",
        "PresentationFacade(",
        "PlatformInterface(",
        "ApplicationInterfaceService(",
        "PlatformKernelFacade(",
        "LifecycleManager(",
        "LifecycleExecutor(",
        "HealthCoordinator(",
        "PlatformHealthFacade(",
    ]
    for pattern in forbidden_instantiations:
        assert pattern not in source


def test_factory_retorna_platform_lifecycle():
    lifecycle = build_default_platform_lifecycle()

    assert isinstance(lifecycle, PlatformLifecycle)


def test_factory_injeta_lifecycle_manager():
    lifecycle = build_default_platform_lifecycle()

    assert isinstance(lifecycle.lifecycle_manager, LifecycleManager)


def test_factory_injeta_lifecycle_executor():
    lifecycle = build_default_platform_lifecycle()

    assert isinstance(lifecycle.lifecycle_executor, LifecycleExecutor)


def test_factory_injeta_health_coordinator():
    lifecycle = build_default_platform_lifecycle()

    assert isinstance(lifecycle.health_coordinator, HealthCoordinator)


def test_factory_injeta_platform_health():
    lifecycle = build_default_platform_lifecycle()

    assert isinstance(lifecycle.platform_health, PlatformHealthFacade)


def test_platform_lifecycle_factory_conhece_apenas_factories_de_health():
    from app.platform.lifecycle import platform_lifecycle_factory as _factory_module

    source = inspect.getsource(_factory_module)

    assert "build_default_health_coordinator" in source
    assert "build_default_platform_health_facade" in source
    assert "HealthCoordinator" not in source
    assert "HealthMonitor" not in source
    assert "HealthReportService" not in source
    assert "HealthExecutor" not in source
    assert "HealthManager" not in source
    assert "HealthCheckRegistry" not in source
    assert "HealthCheck" not in source
    assert "PlatformHealthFacade" not in source


def test_lifecycle_factory_usa_apenas_a_factory_do_kernel_facade(monkeypatch):
    from app.platform.bootstrap import platform_kernel_facade_factory

    calls = {"count": 0}
    original = platform_kernel_facade_factory.build_default_platform_kernel_facade

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_lifecycle_factory, "build_default_platform_kernel_facade", _spy
    )

    build_default_platform_lifecycle()

    assert calls["count"] == 1


def test_lifecycle_factory_usa_apenas_a_factory_do_lifecycle_manager(monkeypatch):
    from app.platform.lifecycle import lifecycle_manager_factory

    calls = {"count": 0}
    original = lifecycle_manager_factory.build_default_lifecycle_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_lifecycle_factory, "build_default_lifecycle_manager", _spy
    )

    build_default_platform_lifecycle()

    assert calls["count"] == 1


def test_lifecycle_factory_usa_apenas_a_factory_do_lifecycle_executor(monkeypatch):
    from app.platform.lifecycle import lifecycle_executor_factory

    calls = {"count": 0}
    original = lifecycle_executor_factory.build_default_lifecycle_executor

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_lifecycle_factory, "build_default_lifecycle_executor", _spy
    )

    build_default_platform_lifecycle()

    assert calls["count"] == 1


def test_lifecycle_factory_usa_apenas_a_factory_do_health_coordinator(monkeypatch):
    from app.platform.health import health_coordinator_factory

    calls = {"count": 0}
    original = health_coordinator_factory.build_default_health_coordinator

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_lifecycle_factory, "build_default_health_coordinator", _spy
    )

    build_default_platform_lifecycle()

    assert calls["count"] == 1


def test_lifecycle_factory_usa_apenas_a_factory_do_platform_health(monkeypatch):
    from app.platform.health import platform_health_facade_factory

    calls = {"count": 0}
    original = platform_health_facade_factory.build_default_platform_health_facade

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        platform_lifecycle_factory, "build_default_platform_health_facade", _spy
    )

    build_default_platform_lifecycle()

    assert calls["count"] == 1
