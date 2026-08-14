import inspect

import pytest

from app.platform.pipeline import pipeline_registry_factory
from app.platform.pipeline.default_stage_provider import DefaultStageProvider
from app.platform.pipeline.pipeline_registry_factory import build_default_pipeline_registry
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.stage_provider import StageProvider


def test_stage_provider_e_abstrato():
    with pytest.raises(TypeError):
        StageProvider()


def test_default_stage_provider_e_um_stage_provider():
    assert isinstance(DefaultStageProvider(), StageProvider)


def test_default_stage_provider_retorna_exatamente_os_quatro_stages_na_ordem():
    stages = DefaultStageProvider().stages()

    assert [stage.name() for stage in stages] == [
        "operations",
        "decision",
        "runtime",
        "observability",
    ]


def test_default_stage_provider_retorna_uma_tupla():
    stages = DefaultStageProvider().stages()

    assert isinstance(stages, tuple)


def test_build_default_pipeline_registry_usa_default_stage_provider_por_padrao():
    registry = build_default_pipeline_registry()

    names = [stage.name() for stage in registry.list()]
    assert names == ["operations", "decision", "runtime", "observability"]


class _CustomStage(PipelineStage):
    def __init__(self, stage_name: str) -> None:
        self._name = stage_name

    def name(self) -> str:
        return self._name

    async def execute(self, session, context, state):
        return state


class _CustomStageProvider(StageProvider):
    def stages(self) -> tuple[PipelineStage, ...]:
        return (_CustomStage("custom_a"), _CustomStage("custom_b"))


def test_injecao_de_provider_customizado():
    registry = build_default_pipeline_registry(stage_provider=_CustomStageProvider())

    names = [stage.name() for stage in registry.list()]
    assert names == ["custom_a", "custom_b"]


def test_pipeline_registry_factory_conhece_apenas_stage_provider():
    source = inspect.getsource(pipeline_registry_factory)
    assert "app.operations" not in source
    assert "app.decision" not in source
    assert "app.runtime" not in source
    assert "app.observability" not in source


def test_nenhuma_referencia_aos_quatro_stages_na_registry_factory():
    source = inspect.getsource(pipeline_registry_factory)
    assert "OperationsStage" not in source
    assert "DecisionStage" not in source
    assert "RuntimeStage" not in source
    assert "ObservabilityStage" not in source
