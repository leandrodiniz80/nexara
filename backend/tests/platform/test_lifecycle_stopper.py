import inspect

from app.platform.lifecycle import lifecycle_stopper, lifecycle_stopper_factory
from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry
from app.platform.lifecycle.lifecycle_stopper import LifecycleStopper
from app.platform.lifecycle.lifecycle_stopper_factory import build_default_lifecycle_stopper


class _Participant(LifecycleParticipant):
    def __init__(self, label: str) -> None:
        self.label = label
        self.stop_calls = 0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self.stop_calls += 1


def _stopper(*participants: LifecycleParticipant) -> LifecycleStopper:
    registry = LifecycleParticipantRegistry().register_many(list(participants))
    manager = LifecycleManager(registry=registry)
    return LifecycleStopper(manager=manager)


def test_lista_vazia():
    stopper = _stopper()

    assert stopper.stop_all() == ()


def test_um_participante():
    participant = _Participant("a")
    stopper = _stopper(participant)

    result = stopper.stop_all()

    assert result == (participant,)
    assert participant.stop_calls == 1


def test_varios_participantes():
    participant_a = _Participant("a")
    participant_b = _Participant("b")
    participant_c = _Participant("c")
    stopper = _stopper(participant_a, participant_b, participant_c)

    result = stopper.stop_all()

    assert result == (participant_a, participant_b, participant_c)
    assert participant_a.stop_calls == 1
    assert participant_b.stop_calls == 1
    assert participant_c.stop_calls == 1


def test_ordem_preservada():
    participant_a = _Participant("a")
    participant_b = _Participant("b")
    stopper = _stopper(participant_a, participant_b)

    result = stopper.stop_all()

    assert [p.label for p in result] == ["a", "b"]


def test_stop_chamado_exatamente_uma_vez():
    participant = _Participant("a")
    stopper = _stopper(participant)

    stopper.stop_all()

    assert participant.stop_calls == 1


def test_retorno_preserva_exatamente_os_participantes():
    participant = _Participant("a")
    stopper = _stopper(participant)

    result = stopper.stop_all()

    assert result[0] is participant


def test_factory_retorna_lifecycle_stopper():
    stopper = build_default_lifecycle_stopper()

    assert isinstance(stopper, LifecycleStopper)


def test_factory_usa_exclusivamente_build_default_lifecycle_manager():
    source = inspect.getsource(lifecycle_stopper_factory)

    assert "build_default_lifecycle_manager" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source
    assert "LifecycleStarter" not in source


def test_manager_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = lifecycle_stopper_factory.build_default_lifecycle_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(lifecycle_stopper_factory, "build_default_lifecycle_manager", _spy)

    build_default_lifecycle_stopper()

    assert calls["count"] == 1


def test_conhece_exclusivamente_lifecycle_manager():
    source = inspect.getsource(lifecycle_stopper)

    assert "LifecycleManager" in source
    assert "PlatformContainer" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(lifecycle_stopper)
    assert "PlatformLifecycle" not in source


def test_nenhuma_referencia_a_lifecycle_starter():
    source = inspect.getsource(lifecycle_stopper)
    assert "LifecycleStarter" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(lifecycle_stopper)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(lifecycle_stopper)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(lifecycle_stopper)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(lifecycle_stopper)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(lifecycle_stopper)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(lifecycle_stopper)
    assert "app.automation" not in source


def test_nenhum_start_ou_restart():
    source = inspect.getsource(lifecycle_stopper)
    assert "def start" not in source
    assert "def restart" not in source
