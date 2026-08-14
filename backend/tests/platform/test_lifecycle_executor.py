import inspect

from app.platform.lifecycle import lifecycle_executor, lifecycle_executor_factory
from app.platform.lifecycle.lifecycle_executor import LifecycleExecutor
from app.platform.lifecycle.lifecycle_executor_factory import build_default_lifecycle_executor
from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry
from app.platform.lifecycle.lifecycle_starter import LifecycleStarter
from app.platform.lifecycle.lifecycle_stopper import LifecycleStopper


class _Participant(LifecycleParticipant):
    def __init__(self, label: str) -> None:
        self.label = label
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


def _manager(*participants: LifecycleParticipant) -> LifecycleManager:
    registry = LifecycleParticipantRegistry().register_many(list(participants))
    return LifecycleManager(registry=registry)


def _executor(*participants: LifecycleParticipant) -> LifecycleExecutor:
    manager = _manager(*participants)
    return LifecycleExecutor(
        starter=LifecycleStarter(manager=manager), stopper=LifecycleStopper(manager=manager)
    )


def test_start():
    participant = _Participant("a")
    executor = _executor(participant)

    result = executor.start()

    assert result == (participant,)
    assert participant.start_calls == 1
    assert participant.stop_calls == 0


def test_stop():
    participant = _Participant("a")
    executor = _executor(participant)

    result = executor.stop()

    assert result == (participant,)
    assert participant.stop_calls == 1
    assert participant.start_calls == 0


def test_retorno_preservado():
    participant_a = _Participant("a")
    participant_b = _Participant("b")
    executor = _executor(participant_a, participant_b)

    start_result = executor.start()
    stop_result = executor.stop()

    assert start_result == (participant_a, participant_b)
    assert stop_result == (participant_a, participant_b)


def test_starter_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = LifecycleStarter.start_all

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(LifecycleStarter, "start_all", _spy)

    executor = _executor(_Participant("a"))
    executor.start()

    assert calls["count"] == 1


def test_stopper_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = LifecycleStopper.stop_all

    def _spy(self):
        calls["count"] += 1
        return original(self)

    monkeypatch.setattr(LifecycleStopper, "stop_all", _spy)

    executor = _executor(_Participant("a"))
    executor.stop()

    assert calls["count"] == 1


def test_factory_retorna_lifecycle_executor():
    executor = build_default_lifecycle_executor()

    assert isinstance(executor, LifecycleExecutor)


def test_factory_usa_exclusivamente_starter_e_stopper_factories(monkeypatch):
    starter_calls = {"count": 0}
    stopper_calls = {"count": 0}
    original_starter = lifecycle_executor_factory.build_default_lifecycle_starter
    original_stopper = lifecycle_executor_factory.build_default_lifecycle_stopper

    def _spy_starter():
        starter_calls["count"] += 1
        return original_starter()

    def _spy_stopper():
        stopper_calls["count"] += 1
        return original_stopper()

    monkeypatch.setattr(
        lifecycle_executor_factory, "build_default_lifecycle_starter", _spy_starter
    )
    monkeypatch.setattr(
        lifecycle_executor_factory, "build_default_lifecycle_stopper", _spy_stopper
    )

    build_default_lifecycle_executor()

    assert starter_calls["count"] == 1
    assert stopper_calls["count"] == 1


def test_factory_source_usa_exclusivamente_as_duas_factories():
    source = inspect.getsource(lifecycle_executor_factory)

    assert "build_default_lifecycle_starter" in source
    assert "build_default_lifecycle_stopper" in source
    assert "build_default_lifecycle_manager" not in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source


def test_conhece_exclusivamente_starter_e_stopper():
    source = inspect.getsource(lifecycle_executor)

    assert "LifecycleStarter" in source
    assert "LifecycleStopper" in source
    assert "LifecycleManager" not in source
    assert "LifecycleParticipant" not in source
    assert "PlatformContainer" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(lifecycle_executor)
    assert "PlatformLifecycle" not in source


def test_nenhuma_referencia_a_lifecycle_manager():
    source = inspect.getsource(lifecycle_executor)
    assert "LifecycleManager" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(lifecycle_executor)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(lifecycle_executor)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(lifecycle_executor)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(lifecycle_executor)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(lifecycle_executor)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(lifecycle_executor)
    assert "app.automation" not in source


def test_nenhum_restart():
    source = inspect.getsource(lifecycle_executor)
    assert "def restart" not in source
