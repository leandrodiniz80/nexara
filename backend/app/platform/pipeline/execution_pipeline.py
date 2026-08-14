from typing import Any

from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession


class ExecutionPipeline:
    """Runs every registered PipelineStage, in the order it was given,
    threading a single `state` dict through each one. It knows nothing
    about Operations, Runtime, Decision, or Observability — each stage's
    own domain knowledge is entirely opaque to it; this class only ever
    calls `stage.execute(session, context, state)` and passes the result
    on to the next stage.
    """

    def __init__(self, stages: list[PipelineStage]) -> None:
        self._stages = stages

    async def execute(
        self, session: ExecutionSession, context: PlatformExecutionContext
    ) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for stage in self._stages:
            state = await stage.execute(session, context, state)
        return state

    def list_stages(self) -> list[PipelineStage]:
        return list(self._stages)
