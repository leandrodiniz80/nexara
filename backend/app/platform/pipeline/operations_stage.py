from typing import Any

from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operations_coordinator import OperationsCoordinator
from app.operations.coordinator.operations_coordinator_factory import (
    build_default_operations_coordinator,
)
from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.pipeline.pipeline_stage import PipelineStage
from app.platform.session.execution_session import ExecutionSession

_OPERATION_NAME = "platform_execute"


class OperationsStage(PipelineStage):
    """Private to app.platform.pipeline — never referenced outside
    `default_stage_discovery.py`, the only place authorized to know this
    class exists. Wraps OperationsCoordinator exactly as
    PlatformExecutionOrchestrator used to call it directly, before the
    pipeline architecture existed. Supports zero-arg construction (falling
    back to OperationsCoordinator's own official factory) so a generic
    discovery mechanism can instantiate it without knowing its collaborator.
    """

    def __init__(self, operations_coordinator: OperationsCoordinator | None = None) -> None:
        self._operations_coordinator = (
            operations_coordinator or build_default_operations_coordinator()
        )

    def name(self) -> str:
        return "operations"

    async def execute(
        self,
        session: ExecutionSession,
        context: PlatformExecutionContext,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        operation_result = self._operations_coordinator.run(
            OperationContext(operation_name=_OPERATION_NAME, metadata=context.metadata)
        )
        new_state = dict(state)
        new_state["operation_result"] = operation_result
        if not operation_result.success or operation_result.history is None:
            new_state["success"] = False
            new_state["stopped"] = True
        return new_state
