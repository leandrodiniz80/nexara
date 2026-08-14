import inspect

from app.platform.lifecycle import lifecycle_starter, lifecycle_starter_factory
from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry
from app.platform.lifecycle.lifecycle_starter import LifecycleStarter
from app.platform.lifecycle.lifecycle_starter_factory import build_default_lifecycle_starter


class _Participant(LifecycleParticipant):
    def __init__(self, label: str) -> None:
        self.label = label
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        pass


def _starter(*participants: LifecycleParticipant) -> LifecycleStarter:
    registry = LifecycleParticipantRegistry().register_many(list(participants))
    manager = LifecycleManager(registry=registry)
    return LifecycleStarter(manager=manager)


def test_lista_vazia():
    starter = _starter()

    assert starter.start_all() == ()


def test_um_participante():
    participant = _Participant("a")
    starter = _starter(participant)

    result = starter.start_all()

    assert result == (participant,)
    assert participant.start_calls == 1


def test_varios_participantes():
    participant_a = _Participant("a")
    participant_b = _Participant("b")
    participant_c = _Participant("c")
    starter = _starter(participant_a, participant_b, participant_c)

    result = starter.start_all()

    assert result == (participant_a, participant_b, participant_c)
    assert participant_a.start_calls == 1
    assert participant_b.start_calls == 1
    assert participant_c.start_calls == 1


def test_ordem_preservada():
    participant_a = _Participant("a")
    participant_b = _Participant("b")
    starter = _starter(participant_a, participant_b)

    result = starter.start_all()

    assert [p.label for p in result] == ["a", "b"]


def test_start_chamado_exatamente_uma_vez():
    participant = _Participant("a")
    starter = _starter(participant)

    starter.start_all()

    assert participant.start_calls == 1


def test_retorno_preserva_exatamente_os_participantes():
    participant = _Participant("a")
    starter = _starter(participant)

    result = starter.start_all()

    assert result[0] is participant


def test_factory_retorna_lifecycle_starter():
    starter = build_default_lifecycle_starter()

    assert isinstance(starter, LifecycleStarter)


def test_factory_usa_exclusivamente_build_default_lifecycle_manager():
    source = inspect.getsource(lifecycle_starter_factory)

    assert "build_default_lifecycle_manager" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "app.decision" not in source
    assert "app.automation" not in source
    assert "PlatformLifecycle" not in source


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = lifecycle_starter_factory.build_default_lifecycle_manager

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(lifecycle_starter_factory, "build_default_lifecycle_manager", _spy)

    build_default_lifecycle_starter()

    assert calls["count"] == 1


def test_conhece_exclusivamente_lifecycle_manager():
    source = inspect.getsource(lifecycle_starter)

    assert "LifecycleManager" in source
    assert "PlatformContainer" not in source
    assert "PlatformBootstrap" not in source
    assert "PlatformKernelFacade" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(lifecycle_starter)
    assert "PlatformLifecycle" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(lifecycle_starter)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(lifecycle_starter)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(lifecycle_starter)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(lifecycle_starter)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_decision():
    source = inspect.getsource(lifecycle_starter)
    assert "app.decision" not in source


def test_nenhuma_referencia_a_automation():
    source = inspect.getsource(lifecycle_starter)
    assert "app.automation" not in source


def test_nenhum_stop_ou_restart():
    source = inspect.getsource(lifecycle_starter)
    assert "def stop" not in source
    assert "def restart" not in source
