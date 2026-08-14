import inspect

import pytest

from app.platform.modules import default_platform_module
from app.platform.modules.default_platform_module import DefaultPlatformModule
from app.platform.modules.platform_module import PlatformModule
from app.platform.pipeline.decision_stage import DecisionStage
from app.platform.pipeline.observability_stage import ObservabilityStage
from app.platform.pipeline.operations_stage import OperationsStage
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.runtime_stage import RuntimeStage
from app.platform.pipeline.stage_provider import StageProvider


def test_platform_module_e_abstrato():
    with pytest.raises(TypeError):
        PlatformModule()


def test_default_platform_module_e_um_platform_module():
    assert isinstance(DefaultPlatformModule(), PlatformModule)


def test_default_platform_module_name():
    assert DefaultPlatformModule().name() == "default"


def test_default_platform_module_stage_provider_e_um_stage_provider():
    module = DefaultPlatformModule()

    assert isinstance(module.stage_provider(), StageProvider)


def test_default_platform_module_stage_provider_produces_the_four_official_stages():
    module = DefaultPlatformModule()

    stages = module.stage_provider().stages()

    assert [type(stage) for stage in stages] == [
        OperationsStage,
        DecisionStage,
        RuntimeStage,
        ObservabilityStage,
    ]


class _CustomStageProvider(StageProvider):
    def stages(self) -> tuple[PipelineStage, ...]:
        return ()


def test_injecao_de_stage_provider_customizado():
    custom = _CustomStageProvider()

    module = DefaultPlatformModule(stage_provider=custom)

    assert module.stage_provider() is custom


def test_default_platform_module_nao_duplica_operations_stage():
    stages = DefaultPlatformModule().stage_provider().stages()

    operations_stage_count = sum(1 for stage in stages if isinstance(stage, OperationsStage))
    assert operations_stage_count == 1


def test_default_platform_module_continua_funcional_ordem_preservada():
    stages = DefaultPlatformModule().stage_provider().stages()

    assert [stage.name() for stage in stages] == [
        "operations",
        "decision",
        "runtime",
        "observability",
    ]


def test_default_platform_module_representa_apenas_um_modulo():
    source = inspect.getsource(default_platform_module)
    assert "OperationsModule" not in source
    assert "CompositeStageProvider" not in source
    assert "CompositePlatformModule" not in source
    assert "app.operations" not in source
