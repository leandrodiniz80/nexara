import pytest
from pydantic import ValidationError

from app.platform.modules.composite_platform_module import CompositePlatformModule
from app.platform.modules.default_platform_module import DefaultPlatformModule
from app.platform.modules.module_registry import ModuleRegistry
from app.platform.modules.module_registry_factory import build_default_module_registry
from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_provider import StageProvider


class _EmptyStageProvider(StageProvider):
    def stages(self) -> tuple[PipelineStage, ...]:
        return ()


class _DummyModule(PlatformModule):
    def __init__(self, module_name: str) -> None:
        self._name = module_name

    def name(self) -> str:
        return self._name

    def stage_provider(self) -> StageProvider:
        return _EmptyStageProvider()


class _NamedStage(PipelineStage):
    def __init__(self, stage_name: str) -> None:
        self._name = stage_name

    def name(self) -> str:
        return self._name

    async def execute(self, session, context, state):
        return state


class _FixedStageProvider(StageProvider):
    def __init__(self, *stage_names: str) -> None:
        self._stages = tuple(_NamedStage(stage_name) for stage_name in stage_names)

    def stages(self) -> tuple[PipelineStage, ...]:
        return self._stages


class _FixedModule(PlatformModule):
    def __init__(self, module_name: str, *stage_names: str) -> None:
        self._name = module_name
        self._stage_provider = _FixedStageProvider(*stage_names)

    def name(self) -> str:
        return self._name

    def stage_provider(self) -> StageProvider:
        return self._stage_provider


def test_registro_adds_the_given_module():
    module = _DummyModule("alpha")
    registry = ModuleRegistry()

    updated = registry.register(module)

    assert updated.list() == [module]
    assert registry.list() == []


def test_registro_many_adds_every_given_module_in_order():
    module_a = _DummyModule("alpha")
    module_b = _DummyModule("beta")
    registry = ModuleRegistry()

    updated = registry.register_many([module_a, module_b])

    assert updated.list() == [module_a, module_b]


def test_find_existente_returns_the_matching_module():
    module = _DummyModule("alpha")
    registry = ModuleRegistry().register(module)

    assert registry.find("alpha") is module


def test_find_inexistente_returns_none():
    registry = ModuleRegistry().register(_DummyModule("alpha"))

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = ModuleRegistry().register(_DummyModule("alpha"))

    assert registry.exists("alpha") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = ModuleRegistry()
    registry = registry.register(_DummyModule("alpha"))
    registry = registry.register(_DummyModule("beta"))
    registry = registry.register(_DummyModule("gamma"))

    assert [module.name() for module in registry.list()] == ["alpha", "beta", "gamma"]


def test_register_never_mutates_the_previous_registry():
    original = ModuleRegistry()

    updated = original.register(_DummyModule("alpha"))

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_objetos_frozen_rejects_attribute_assignment():
    registry = ModuleRegistry().register(_DummyModule("alpha"))

    with pytest.raises(ValidationError):
        registry.modules = ()


def test_injecao_uses_exactly_the_modules_provided():
    module = _DummyModule("alpha")

    registry = ModuleRegistry().register(module)

    assert registry.list() == [module]


def test_build_default_module_registry_registers_the_default_platform_module():
    registry = build_default_module_registry()

    assert registry.exists("default") is True
    module = registry.find("default")
    assert isinstance(module, DefaultPlatformModule)


def test_composite_returns_a_composite_platform_module():
    registry = ModuleRegistry().register(_DummyModule("alpha"))

    composite = registry.composite()

    assert isinstance(composite, CompositePlatformModule)


def test_composite_unifica_stages_de_todos_os_modulos_registrados_em_ordem():
    registry = ModuleRegistry().register_many(
        [_FixedModule("a", "alpha", "beta"), _FixedModule("b", "gamma")]
    )

    composite = registry.composite()

    names = [stage.name() for stage in composite.stage_provider().stages()]
    assert names == ["alpha", "beta", "gamma"]


def test_composite_with_empty_registry_produces_no_stages():
    registry = ModuleRegistry()

    composite = registry.composite()

    assert composite.stage_provider().stages() == ()
