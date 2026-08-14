import inspect

import pytest

from app.platform.pipeline import default_stage_provider
from app.platform.pipeline.default_stage_discovery import DefaultStageDiscovery
from app.platform.pipeline.default_stage_provider import DefaultStageProvider
from app.platform.pipeline.decision_stage import DecisionStage
from app.platform.pipeline.observability_stage import ObservabilityStage
from app.platform.pipeline.operations_stage import OperationsStage
from app.platform.pipeline.pipeline_registry_factory import build_default_pipeline_registry
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.pipeline.runtime_stage import RuntimeStage
from app.platform.pipeline.stage_discovery import StageDiscovery


def test_stage_discovery_e_abstrato():
    with pytest.raises(TypeError):
        StageDiscovery()


def test_default_stage_discovery_e_uma_stage_discovery():
    assert isinstance(DefaultStageDiscovery(), StageDiscovery)


def test_default_stage_discovery_retorna_exatamente_as_quatro_classes_na_ordem():
    classes = DefaultStageDiscovery().discover()

    assert classes == (OperationsStage, DecisionStage, RuntimeStage, ObservabilityStage)


def test_default_stage_discovery_retorna_uma_tupla():
    classes = DefaultStageDiscovery().discover()

    assert isinstance(classes, tuple)


def test_default_stage_provider_retorna_instancias_das_quatro_classes_na_ordem():
    stages = DefaultStageProvider().stages()

    assert [type(stage) for stage in stages] == [
        OperationsStage,
        DecisionStage,
        RuntimeStage,
        ObservabilityStage,
    ]
    assert [stage.name() for stage in stages] == [
        "operations",
        "decision",
        "runtime",
        "observability",
    ]


class _CustomStage(PipelineStage):
    def name(self) -> str:
        return "custom"

    async def execute(self, session, context, state):
        return state


class _CustomStageDiscovery(StageDiscovery):
    def discover(self) -> tuple[type[PipelineStage], ...]:
        return (_CustomStage,)


def test_injecao_de_discovery_customizada():
    provider = DefaultStageProvider(stage_discovery=_CustomStageDiscovery())

    stages = provider.stages()

    assert [type(stage) for stage in stages] == [_CustomStage]


def test_default_stage_provider_conhece_apenas_stage_discovery():
    source = inspect.getsource(default_stage_provider)
    assert "OperationsStage" not in source
    assert "DecisionStage" not in source
    assert "RuntimeStage" not in source
    assert "ObservabilityStage" not in source
    assert "app.operations" not in source
    assert "app.decision" not in source
    assert "app.runtime" not in source
    assert "app.observability" not in source


def test_factory_continua_funcionando():
    registry = build_default_pipeline_registry()

    names = [stage.name() for stage in registry.list()]
    assert names == ["operations", "decision", "runtime", "observability"]
