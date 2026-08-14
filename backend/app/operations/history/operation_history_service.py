from datetime import datetime, timezone

from app.operations.history.operation_history import OperationHistory
from app.operations.history.operation_history_event import OperationHistoryEvent
from app.operations.models.operation import Operation

_CREATED_EVENT = "created"
_STARTED_EVENT = "started"
_FINISHED_EVENT = "finished"
_FAILED_EVENT = "failed"

_CREATED_MESSAGE = "Operation created."
_STARTED_MESSAGE = "Operation started."
_FINISHED_MESSAGE = "Operation finished."
_DEFAULT_FAILED_MESSAGE = "Operation failed."


class OperationHistoryService:
    """Records what happened during an Operation's lifecycle — nothing
    more. Every method returns a brand new OperationHistory with one more
    OperationHistoryEvent appended to the end; the previous OperationHistory,
    and every event it already held, are left exactly as they were. It
    knows nothing outside app.operations: no Runtime, no Application, no
    CRM, no Workflow, no Presentation.
    """

    def create(self, operation: Operation, *, now: datetime | None = None) -> OperationHistory:
        empty = OperationHistory(operation_id=operation.id, events=())
        return self.record_created(empty, now=now)

    def record_created(
        self, history: OperationHistory, *, now: datetime | None = None
    ) -> OperationHistory:
        return self._append(history, event_type=_CREATED_EVENT, message=_CREATED_MESSAGE, now=now)

    def record_started(
        self, history: OperationHistory, *, now: datetime | None = None
    ) -> OperationHistory:
        return self._append(history, event_type=_STARTED_EVENT, message=_STARTED_MESSAGE, now=now)

    def record_finished(
        self, history: OperationHistory, *, now: datetime | None = None
    ) -> OperationHistory:
        return self._append(
            history, event_type=_FINISHED_EVENT, message=_FINISHED_MESSAGE, now=now
        )

    def record_failed(
        self,
        history: OperationHistory,
        *,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> OperationHistory:
        return self._append(
            history, event_type=_FAILED_EVENT, message=reason or _DEFAULT_FAILED_MESSAGE, now=now
        )

    @staticmethod
    def _append(
        history: OperationHistory,
        *,
        event_type: str,
        message: str,
        now: datetime | None,
    ) -> OperationHistory:
        now = now or datetime.now(timezone.utc)
        event = OperationHistoryEvent(event_type=event_type, timestamp=now, message=message)
        return OperationHistory(
            operation_id=history.operation_id, events=history.events + (event,)
        )
