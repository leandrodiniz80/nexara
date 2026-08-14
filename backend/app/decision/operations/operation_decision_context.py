from pydantic import BaseModel, ConfigDict

from app.observability.operations.operation_trace import OperationTrace
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory


class OperationDecisionContext(BaseModel):
    """A standardized bundle of everything Operations/Observability already
    know about one Operation, ready for Decision to read — frozen, and
    never a decision itself. Building one decides nothing.
    """

    model_config = ConfigDict(frozen=True)

    operation_history: OperationHistory
    operation_result: OperationResult
    operation_trace: OperationTrace
