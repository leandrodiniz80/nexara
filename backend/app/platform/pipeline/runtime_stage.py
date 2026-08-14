from typing import Any

from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.services.runtime_engine_factory import build_default_runtime_engine


class RuntimeStage(PipelineStage):
    """Private to app.platform.pipeline — never referenced outside
    `default_stage_discovery.py`, the only place authorized to know this
    class exists. Wraps RuntimeEngine exactly as
    PlatformExecutionOrchestrator used to call it directly, before the
    pipeline architecture existed. Supports zero-arg construction (falling
    back to RuntimeEngine's own official factory) so a generic discovery
    mechanism can instantiate it without knowing its collaborator.
    """

    def __init__(self, runtime_engine: RuntimeEngine | None = None) -> None:
        self._runtime_engine = runtime_engine or build_default_runtime_engine()

    def name(self) -> str:
        return "runtime"

    async def execute(
        self,
        session: ExecutionSession,
        context: PlatformExecutionContext,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if state.get("stopped"):
            return state

        execution_type, execution_context = context.payload
        runtime_result = await self._runtime_engine.execute(execution_type, execution_context)
        new_state = dict(state)
        new_state["runtime_result"] = runtime_result
        if not runtime_result.success:
            new_state["success"] = False
            new_state["stopped"] = True
        return new_state
