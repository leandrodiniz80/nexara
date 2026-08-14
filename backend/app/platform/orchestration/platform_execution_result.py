from pydantic import BaseModel, ConfigDict

from app.decision.models.decision_result import DecisionResult
from app.observability.models.execution_trace import ExecutionTrace
from app.operations.coordinator.operation_result import OperationResult
from app.platform.session.execution_session import ExecutionSession
from app.runtime.models.execution_result import ExecutionResult


class PlatformExecutionResult(BaseModel):
    """The frozen outcome of running one PlatformExecutionContext through
    PlatformExecutionOrchestrator — every collaborator's own result,
    whichever ones were actually reached before the pipeline stopped (on
    success, or on the first failing step other than Observability, which
    never interrupts the overall result). `execution_session` is always
    present and always finished, regardless of where the pipeline stopped.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    request_id: str | None = None
    operation_result: OperationResult | None = None
    decision_result: DecisionResult | None = None
    runtime_result: ExecutionResult | None = None
    observability_result: ExecutionTrace | None = None
    execution_time: float
    execution_session: ExecutionSession
