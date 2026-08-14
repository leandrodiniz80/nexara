import inspect

import pytest
from pydantic import ValidationError

from app.platform.lifecycle import lifecycle_manager, lifecycle_manager_factory
from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_manager_factory import build_default_lifecycle_manager
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry


class _ParticipantA(LifecycleParticipant):
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


class _ParticipantB(LifecycleParticipant):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def _registry(*participants: LifecycleParticipant) -> LifecycleParticipantRegistry:
    return LifecycleParticipantRegistry().register_many(list(participants))


def test_participant_existente():
    participant = _ParticipantA()
    manager = LifecycleManager(registry=_registry(participant))

    assert manager.participant("_ParticipantA") is participant


def test_participant_inexistente_retorna_none_sem_key_error():
    manager = LifecycleManager(registry=_registry(_ParticipantA()))

    result = manager.participant("does_not_exist")

    assert result is None


def test_exists():
    manager = LifecycleManager(registry=_registry(_ParticipantA()))

    assert manager.exists("_ParticipantA") is True
    assert manager.exists("does_not_exist") is False


def test_participants():
    participant_a = _ParticipantA()
    participant_b = _ParticipantB()
    manager = LifecycleManager(registry=_registry(participant_a, participant_b))

    assert manager.participants() == [participant_a, participant_b]


def test_participant_nunca_chama_start_ou_stop():
    participant = _ParticipantA()
    manager = LifecycleManager(registry=_registry(participant))

    manager.participant("_ParticipantA")
    manager.exists("_ParticipantA")
    manager.participants()

    assert participant.start_calls == 0
    assert participant.stop_calls == 0


def test_singleton_nao_e_responsabilidade_desta_classe():
    manager = LifecycleManager(registry=_registry(_ParticipantA()))

    assert manager.participants() is not manager.participants()


def test_imutabilidade_rejects_attribute_assignment():
    manager = LifecycleManager(registry=_registry(_ParticipantA()))

    with pytest.raises(ValidationError):
        manager.registry = LifecycleParticipantRegistry()


def test_injecao_uses_exactly_the_registry_provided():
    registry = _registry(_ParticipantA())

    manager = LifecycleManager(registry=registry)

    assert manager.registry is registry


def test_conhece_exclusivamente_lifecycle_participant_registry():
    source = inspect.getsource(lifecycle_manager)

    assert "LifecycleParticipantRegistry" in source
    assert "LifecycleParticipant" in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(lifecycle_manager)
    assert "PlatformLifecycle" not in source


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(lifecycle_manager)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(lifecycle_manager)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(lifecycle_manager)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(lifecycle_manager)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_bootstrap():
    source = inspect.getsource(lifecycle_manager)
    assert "Bootstrap" not in source
    assert "app.platform.bootstrap" not in source


def test_nenhuma_referencia_a_platform_kernel():
    source = inspect.getsource(lifecycle_manager)
    assert "PlatformKernel" not in source


def test_factory_retorna_lifecycle_manager():
    manager = build_default_lifecycle_manager()

    assert isinstance(manager, LifecycleManager)


def test_factory_usa_exclusivamente_build_default_lifecycle_participant_registry():
    source = inspect.getsource(lifecycle_manager_factory)

    assert "build_default_lifecycle_participant_registry" in source
    assert "app.runtime" not in source
    assert "app.operations" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source
    assert "Bootstrap" not in source
    assert "PlatformKernel" not in source
    assert "PlatformLifecycle" not in source


def test_registry_chamado_exatamente_uma_vez(monkeypatch):
    calls = {"count": 0}
    original = lifecycle_manager_factory.build_default_lifecycle_participant_registry

    def _spy():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(
        lifecycle_manager_factory, "build_default_lifecycle_participant_registry", _spy
    )

    build_default_lifecycle_manager()

    assert calls["count"] == 1
