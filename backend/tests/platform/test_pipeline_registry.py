import inspect
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline import execution_pipeline_factory, pipeline_registry
from app.platform.pipeline.execution_pipeline import ExecutionPipeline
from app.platform.pipeline.execution_pipeline_factory import build_default_execution_pipeline
from app.platform.pipeline.pipeline_registry import PipelineRegistry
from app.platform.pipeline.pipeline_registry_factory import build_default_pipeline_registry
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _session() -> ExecutionSession:
    return ExecutionSession(started_at=_T0)


class _DummyStage(PipelineStage):
    def __init__(self, stage_name: str) -> None:
        self._name = stage_name

    def name(self) -> str:
        return self._name

    async def execute(
        self, session: ExecutionSession, context: PlatformExecutionContext, state: dict[str, Any]
    ) -> dict[str, Any]:
        return state


def test_registro_adds_the_given_stage():
    stage = _DummyStage("alpha")
    registry = PipelineRegistry()

    updated = registry.register(stage)

    assert updated.list() == [stage]
    assert registry.list() == []


def test_registro_many_adds_every_given_stage_in_order():
    stage_a = _DummyStage("alpha")
    stage_b = _DummyStage("beta")
    registry = PipelineRegistry()

    updated = registry.register_many([stage_a, stage_b])

    assert updated.list() == [stage_a, stage_b]


def test_find_existente_returns_the_matching_stage():
    stage = _DummyStage("alpha")
    registry = PipelineRegistry().register(stage)

    assert registry.find("alpha") is stage


def test_find_inexistente_returns_none():
    registry = PipelineRegistry().register(_DummyStage("alpha"))

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = PipelineRegistry().register(_DummyStage("alpha"))

    assert registry.exists("alpha") is True
    assert registry.exists("does_not_exist") is False


def test_ordem_preservada_across_multiple_registrations():
    registry = PipelineRegistry()
    registry = registry.register(_DummyStage("alpha"))
    registry = registry.register(_DummyStage("beta"))
    registry = registry.register(_DummyStage("gamma"))

    assert [stage.name() for stage in registry.list()] == ["alpha", "beta", "gamma"]


def test_register_never_mutates_the_previous_registry():
    original = PipelineRegistry()

    updated = original.register(_DummyStage("alpha"))

    assert original.list() == []
    assert updated.list() != []
    assert original is not updated


def test_objetos_frozen_rejects_attribute_assignment():
    registry = PipelineRegistry().register(_DummyStage("alpha"))

    with pytest.raises(ValidationError):
        registry.stages = ()


def test_build_default_pipeline_registry_registers_the_four_stages_in_order():
    registry = build_default_pipeline_registry()

    names = [stage.name() for stage in registry.list()]
    assert names == ["operations", "decision", "runtime", "observability"]
    assert registry.exists("operations") is True
    assert registry.find("runtime") is not None


def test_injecao_uses_exactly_the_registry_provided():
    stage = _DummyStage("alpha")
    registry = PipelineRegistry().register(stage)

    pipeline = build_default_execution_pipeline(pipeline_registry=registry)

    assert isinstance(pipeline, ExecutionPipeline)
    assert pipeline.list_stages() == [stage]


def test_build_default_execution_pipeline_defaults_to_the_default_registry():
    pipeline = build_default_execution_pipeline()

    names = [stage.name() for stage in pipeline.list_stages()]
    assert names == ["operations", "decision", "runtime", "observability"]


def test_pipeline_factory_conhece_apenas_registry():
    source = inspect.getsource(execution_pipeline_factory)
    assert "app.operations" not in source
    assert "app.decision" not in source
    assert "app.runtime" not in source
    assert "app.observability" not in source
    assert "app.crm" not in source
    assert "app.workflows" not in source


def test_nenhuma_referencia_aos_quatro_stages_na_factory():
    source = inspect.getsource(execution_pipeline_factory)
    assert "OperationsStage" not in source
    assert "DecisionStage" not in source
    assert "RuntimeStage" not in source
    assert "ObservabilityStage" not in source


def test_registry_nenhum_import_de_operations():
    source = inspect.getsource(pipeline_registry)
    assert "app.operations" not in source


def test_registry_nenhum_import_de_decision():
    source = inspect.getsource(pipeline_registry)
    assert "app.decision" not in source


def test_registry_nenhum_import_de_runtime():
    source = inspect.getsource(pipeline_registry)
    assert "app.runtime" not in source


def test_registry_nenhum_import_de_observability():
    source = inspect.getsource(pipeline_registry)
    assert "app.observability" not in source
