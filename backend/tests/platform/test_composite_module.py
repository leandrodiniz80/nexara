from app.platform.modules.composite_platform_module import CompositePlatformModule
from app.platform.modules.composite_stage_provider import CompositeStageProvider
from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_provider import StageProvider


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


def test_composite_stage_provider_e_uma_stage_provider():
    assert isinstance(CompositeStageProvider([]), StageProvider)


def test_composite_stage_provider_unifica_stages_de_multiplos_providers():
    provider_a = _FixedStageProvider("alpha", "beta")
    provider_b = _FixedStageProvider("gamma")

    composite = CompositeStageProvider([provider_a, provider_b])

    assert [stage.name() for stage in composite.stages()] == ["alpha", "beta", "gamma"]


def test_composite_stage_provider_preserva_ordem():
    provider_a = _FixedStageProvider("first", "second")
    provider_b = _FixedStageProvider("third", "fourth")

    composite = CompositeStageProvider([provider_a, provider_b])

    assert [stage.name() for stage in composite.stages()] == [
        "first",
        "second",
        "third",
        "fourth",
    ]


def test_composite_stage_provider_remove_duplicados_mantendo_o_primeiro():
    first_alpha = _NamedStage("alpha")
    second_alpha = _NamedStage("alpha")

    class _ProviderA(StageProvider):
        def stages(self) -> tuple[PipelineStage, ...]:
            return (first_alpha,)

    class _ProviderB(StageProvider):
        def stages(self) -> tuple[PipelineStage, ...]:
            return (second_alpha, _NamedStage("beta"))

    composite = CompositeStageProvider([_ProviderA(), _ProviderB()])

    stages = composite.stages()
    assert [stage.name() for stage in stages] == ["alpha", "beta"]
    assert stages[0] is first_alpha


def test_composite_stage_provider_com_lista_vazia():
    assert CompositeStageProvider([]).stages() == ()


def test_composite_platform_module_e_um_platform_module():
    assert isinstance(CompositePlatformModule([]), PlatformModule)


def test_composite_platform_module_name():
    assert CompositePlatformModule([]).name() == "composite"


def test_composite_platform_module_unifica_stage_providers_dos_modulos():
    module_a = _FixedModule("a", "alpha", "beta")
    module_b = _FixedModule("b", "gamma")

    composite = CompositePlatformModule([module_a, module_b])

    names = [stage.name() for stage in composite.stage_provider().stages()]
    assert names == ["alpha", "beta", "gamma"]


def test_composite_platform_module_remove_duplicados_entre_modulos():
    module_a = _FixedModule("a", "operations", "decision")
    module_b = _FixedModule("b", "operations", "runtime")

    composite = CompositePlatformModule([module_a, module_b])

    names = [stage.name() for stage in composite.stage_provider().stages()]
    assert names == ["operations", "decision", "runtime"]
