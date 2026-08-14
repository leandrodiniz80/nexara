import time

from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.orchestration.platform_execution_result import PlatformExecutionResult
from app.platform.pipeline.execution_pipeline import ExecutionPipeline
from app.platform.session.execution_session_service import ExecutionSessionService


class PlatformExecutionOrchestrator:
    """The single official point capable of coordinating the whole
    platform. Since this sprint, it knows exclusively ExecutionPipeline and
    ExecutionSessionService — it no longer knows Operations, Decision,
    Runtime, or Observability at all; every integration with those domains
    now happens exclusively through the PipelineStages ExecutionPipeline
    was built with.

    ExecutionSessionService.create() runs first and .finish() runs last,
    exactly once each, on every call to `execute()` — regardless of what
    the pipeline's own stages decide internally. The pipeline's resulting
    `state` dict is read out, never interpreted beyond copying known keys
    into PlatformExecutionResult: whether the pipeline stopped early, and
    why, is entirely each stage's own concern.
    """

    def __init__(
        self,
        execution_pipeline: ExecutionPipeline,
        execution_session_service: ExecutionSessionService,
    ) -> None:
        self._execution_pipeline = execution_pipeline
        self._execution_session_service = execution_session_service

    async def execute(self, context: PlatformExecutionContext) -> PlatformExecutionResult:
        started_at = time.perf_counter()
        session = self._execution_session_service.create(
            request_id=context.request_id, metadata=context.metadata
        )

        state = await self._execution_pipeline.execute(session, context)

        finished_session = self._execution_session_service.finish(session)

        return PlatformExecutionResult(
            success=state.get("success", True),
            request_id=context.request_id,
            operation_result=state.get("operation_result"),
            decision_result=state.get("decision_result"),
            runtime_result=state.get("runtime_result"),
            observability_result=state.get("observability_result"),
            execution_time=time.perf_counter() - started_at,
            execution_session=finished_session,
        )
