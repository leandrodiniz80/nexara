from pydantic import BaseModel, ConfigDict

from app.operations.history.operation_history import OperationHistory
from app.operations.models.operation import Operation
from app.operations.models.operation_status import OperationStatus


class OperationResult(BaseModel):
    """The frozen outcome of running one OperationContext through
    OperationsCoordinator. `operation`/`status` are populated only on
    success; `reason` only on failure — OperationsCoordinator never lets
    an exception escape, it always returns one of these instead. `history`
    carries the full trail of what happened along the way, whenever one
    was recorded — populated on success, and on failure whenever the
    Operation had already been created before the failure occurred.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    operation: Operation | None = None
    status: OperationStatus | None = None
    reason: str | None = None
    execution_time: float
    history: OperationHistory | None = None
