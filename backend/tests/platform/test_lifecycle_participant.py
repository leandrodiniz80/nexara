import inspect

import pytest
from pydantic import ValidationError

from app.platform.lifecycle import lifecycle_participant_registry
from app.platform.lifecycle.lifecycle_participant import LifecycleParticipant
from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry
from app.platform.lifecycle.lifecycle_participant_registry_factory import (
    build_default_lifecycle_participant_registry,
)


class _ParticipantA(LifecycleParticipant):
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class _ParticipantB(LifecycleParticipant):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class _ParticipantC(LifecycleParticipant):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_lifecycle_participant_e_abstrato():
    with pytest.raises(TypeError):
        LifecycleParticipant()


def test_registry_vazio_por_padrao():
    registry = LifecycleParticipantRegistry()

    assert registry.list() == []


def test_registro_adds_the_given_participant():
    participant = _ParticipantA()
    registry = LifecycleParticipantRegistry()

    updated = registry.register(participant)

    assert updated.list() == [participant]
    assert registry.list() == []


def test_register_many_adds_every_given_participant_in_order():
    participant_a = _ParticipantA()
    participant_b = _ParticipantB()
    registry = LifecycleParticipantRegistry()

    updated = registry.register_many([participant_a, participant_b])

    assert updated.list() == [participant_a, participant_b]


def test_find_existente_returns_the_matching_participant():
    participant = _ParticipantA()
    registry = LifecycleParticipantRegistry().register(participant)

    assert registry.find("_ParticipantA") is participant


def test_find_inexistente_returns_none():
    registry = LifecycleParticipantRegistry().register(_ParticipantA())

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = LifecycleParticipantRegistry().register(_ParticipantA())

    assert registry.exists("_ParticipantA") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = LifecycleParticipantRegistry()
    registry = registry.register(_ParticipantA())
    registry = registry.register(_ParticipantB())
    registry = registry.register(_ParticipantC())

    assert [type(p).__name__ for p in registry.list()] == [
        "_ParticipantA",
        "_ParticipantB",
        "_ParticipantC",
    ]


def test_register_never_mutates_the_previous_registry():
    original = LifecycleParticipantRegistry()

    updated = original.register(_ParticipantA())

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_imutabilidade_rejects_attribute_assignment():
    registry = LifecycleParticipantRegistry().register(_ParticipantA())

    with pytest.raises(ValidationError):
        registry.participants = ()


def test_registry_utiliza_exclusivamente_registry_t():
    source = inspect.getsource(lifecycle_participant_registry)

    assert "from app.shared.registry.registry import Registry" in source
    assert "for participant in" not in source
    assert "for item in" not in source


def test_build_default_lifecycle_participant_registry_e_vazio():
    registry = build_default_lifecycle_participant_registry()

    assert isinstance(registry, LifecycleParticipantRegistry)
    assert registry.list() == []


def test_nenhuma_referencia_a_runtime():
    source = inspect.getsource(lifecycle_participant_registry)
    assert "app.runtime" not in source


def test_nenhuma_referencia_a_operations():
    source = inspect.getsource(lifecycle_participant_registry)
    assert "app.operations" not in source


def test_nenhuma_referencia_a_crm():
    source = inspect.getsource(lifecycle_participant_registry)
    assert "app.crm" not in source


def test_nenhuma_referencia_a_workflow():
    source = inspect.getsource(lifecycle_participant_registry)
    assert "app.workflows" not in source


def test_nenhuma_referencia_a_platform_lifecycle():
    source = inspect.getsource(lifecycle_participant_registry)
    assert "PlatformLifecycle" not in source
    assert "from app.platform.lifecycle.platform_lifecycle" not in source
