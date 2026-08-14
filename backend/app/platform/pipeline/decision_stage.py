from typing import Any

from app.decision.operations.decision_operations_service import DecisionOperationsService
from app.decision.operations.decision_operations_service_factory import (
    build_default_decision_operations_service,
)
from app.observability.operations.operation_trace_service import OperationTraceService
from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession


class DecisionStage(PipelineStage):
    """Private to app.platform.pipeline — never referenced outside
    `default_stage_discovery.py`, the only place authorized to know this
    class exists. Wraps DecisionOperationsService exactly as
    PlatformExecutionOrchestrator used to call it directly, including
    building the OperationTrace it requires, before the pipeline
    architecture existed. Supports zero-arg construction (falling back to
    DecisionOperationsService's own official factory) so a generic
    discovery mechanism can instantiate it without knowing its collaborator.
    """

    def __init__(
        self, decision_operations_service: DecisionOperationsService | None = None
    ) -> None:
        self._decision_operations_service = (
            decision_operations_service or build_default_decision_operations_service()
        )
        self._operation_trace_service = OperationTraceService()

    def name(self) -> str:
        return "decision"

    async def execute(
        self,
        session: ExecutionSession,
        context: PlatformExecutionContext,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if state.get("stopped"):
            return state

        operation_result = state["operation_result"]
        trace = self._operation_trace_service.build_trace(
            operation_result.history, operation_result
        )
        decision_result = self._decision_operations_service.evaluate(
            operation_result.history, operation_result, trace
        )
        new_state = dict(state)
        new_state["decision_result"] = decision_result
        if not decision_result.success:
            new_state["success"] = False
            new_state["stopped"] = True
        return new_state
