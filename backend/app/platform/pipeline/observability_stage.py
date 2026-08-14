from typing import Any

from app.observability.operations.observability_operations_service import (
    ObservabilityOperationsService,
)
from app.observability.operations.observability_operations_service_factory import (
    build_default_observability_operations_service,
)
from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession


class ObservabilityStage(PipelineStage):
    """Private to app.platform.pipeline — never referenced outside
    `default_stage_discovery.py`, the only place authorized to know this
    class exists. Wraps ObservabilityOperationsService exactly as
    PlatformExecutionOrchestrator used to call it directly, before the
    pipeline architecture existed: a failure here (including a raised
    exception) never stops the pipeline or flips overall success —
    Observability's own outcome is best-effort. Supports zero-arg
    construction (falling back to ObservabilityOperationsService's own
    official factory) so a generic discovery mechanism can instantiate it
    without knowing its collaborator.
    """

    def __init__(
        self, observability_operations_service: ObservabilityOperationsService | None = None
    ) -> None:
        self._observability_operations_service = (
            observability_operations_service or build_default_observability_operations_service()
        )

    def name(self) -> str:
        return "observability"

    async def execute(
        self,
        session: ExecutionSession,
        context: PlatformExecutionContext,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if state.get("stopped"):
            return state

        operation_result = state["operation_result"]
        new_state = dict(state)
        try:
            observability_result = self._observability_operations_service.record(
                operation_result.history, operation_result
            )
        except Exception:
            observability_result = None
        new_state["observability_result"] = observability_result
        return new_state
