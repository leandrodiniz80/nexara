import inspect
from datetime import datetime, timezone
from typing import Any

from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline import execution_pipeline
from app.platform.pipeline.execution_pipeline import ExecutionPipeline
from app.platform.pipeline.execution_pipeline_factory import build_default_execution_pipeline
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession
from app.runtime.models.enums import ExecutionType
from app.runtime.models.execution_context import ExecutionContext

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def _session() -> ExecutionSession:
    return ExecutionSession(started_at=_T0)


def _payload() -> tuple:
    return (ExecutionType.WORKFLOW, ExecutionContext())


class _RecordingStage(PipelineStage):
    def __init__(self, stage_name: str, key: str, value: Any) -> None:
        self._name = stage_name
        self._key = key
        self._value = value
        self.received_sessions: list[ExecutionSession] = []
        self.received_states: list[dict] = []

    def name(self) -> str:
        return self._name

    async def execute(self, session, context, state):
        self.received_sessions.append(session)
        self.received_states.append(dict(state))
        if state.get("stopped"):
            return state
        new_state = dict(state)
        new_state[self._key] = self._value
        return new_state


async def test_pipeline_executa_stages_na_ordem():
    order: list[str] = []

    class _OrderStage(PipelineStage):
        def __init__(self, stage_name: str) -> None:
            self._name = stage_name

        def name(self) -> str:
            return self._name

        async def execute(self, session, context, state):
            order.append(self._name)
            return state

    pipeline = ExecutionPipeline(
        [_OrderStage("first"), _OrderStage("second"), _OrderStage("third")]
    )
    context = PlatformExecutionContext(payload=_payload())

    await pipeline.execute(_session(), context)

    assert order == ["first", "second", "third"]


async def test_state_preservado_across_stages():
    stage_a = _RecordingStage("a", "a_key", "a_value")
    stage_b = _RecordingStage("b", "b_key", "b_value")
    pipeline = ExecutionPipeline([stage_a, stage_b])
    context = PlatformExecutionContext(payload=_payload())

    final_state = await pipeline.execute(_session(), context)

    assert stage_a.received_states[0] == {}
    assert stage_b.received_states[0] == {"a_key": "a_value"}
    assert final_state == {"a_key": "a_value", "b_key": "b_value"}


async def test_execution_session_preservada_across_stages():
    stage_a = _RecordingStage("a", "a_key", "a_value")
    stage_b = _RecordingStage("b", "b_key", "b_value")
    pipeline = ExecutionPipeline([stage_a, stage_b])
    context = PlatformExecutionContext(payload=_payload())
    session = _session()

    await pipeline.execute(session, context)

    assert stage_a.received_sessions[0] is session
    assert stage_b.received_sessions[0] is session


async def test_a_stage_can_stop_the_pipeline_via_state():
    class _StoppingStage(PipelineStage):
        def name(self) -> str:
            return "stopping"

        async def execute(self, session, context, state):
            return {**state, "success": False, "stopped": True}

    downstream = _RecordingStage("downstream", "downstream_key", "downstream_value")
    pipeline = ExecutionPipeline([_StoppingStage(), downstream])
    context = PlatformExecutionContext(payload=_payload())

    final_state = await pipeline.execute(_session(), context)

    assert final_state["success"] is False
    assert downstream.received_states[0] == {"success": False, "stopped": True}
    assert "downstream_key" not in final_state


def test_injecao_uses_exactly_the_stages_provided():
    stage_a = _RecordingStage("a", "a_key", "a_value")
    stage_b = _RecordingStage("b", "b_key", "b_value")

    pipeline = ExecutionPipeline([stage_a, stage_b])

    assert pipeline.list_stages() == [stage_a, stage_b]


def test_build_default_execution_pipeline_registers_the_four_stages_in_order():
    pipeline = build_default_execution_pipeline()

    names = [stage.name() for stage in pipeline.list_stages()]
    assert names == ["operations", "decision", "runtime", "observability"]


def test_nenhum_import_de_runtime():
    source = inspect.getsource(execution_pipeline)
    assert "app.runtime" not in source


def test_nenhum_import_de_crm():
    source = inspect.getsource(execution_pipeline)
    assert "app.crm" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(execution_pipeline)
    assert "app.workflows" not in source


def test_nenhum_import_de_decision():
    source = inspect.getsource(execution_pipeline)
    assert "app.decision" not in source


def test_nenhum_import_de_observability():
    source = inspect.getsource(execution_pipeline)
    assert "app.observability" not in source
