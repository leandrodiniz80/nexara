from datetime import datetime, timezone

from app.observability.operations.operation_trace import OperationTrace
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory


class OperationTraceService:
    """Builds an OperationTrace from an already-finished OperationHistory
    and OperationResult — nothing more. It knows exclusively
    OperationHistory and OperationResult, and never alters either: no
    field on the given history or result is ever written to, only read.
    """

    def build_trace(self, history: OperationHistory, result: OperationResult) -> OperationTrace:
        if history.events:
            started_at = history.events[0].timestamp
            finished_at = history.events[-1].timestamp
        else:
            started_at = finished_at = datetime.now(timezone.utc)

        metadata = dict(result.operation.metadata) if result.operation is not None else {}

        return OperationTrace(
            operation_id=history.operation_id,
            started_at=started_at,
            finished_at=finished_at,
            duration=result.execution_time,
            success=result.success,
            events=history.events,
            metadata=metadata,
        )
