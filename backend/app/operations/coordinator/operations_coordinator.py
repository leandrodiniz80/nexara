import time

from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operation_result import OperationResult
from app.operations.engine.operations_engine import OperationsEngine
from app.operations.history.operation_history import OperationHistory
from app.operations.history.operation_history_service import OperationHistoryService


class OperationsCoordinator:
    """Coordinates one Operation's full lifecycle — create, start, finish
    — encapsulating that sequence behind a single call, and now
    responsible for producing both the resulting state and the full
    history of how it got there. It knows exclusively OperationsEngine and
    OperationHistoryService: nothing about Runtime, Workflow, CRM,
    Decision, Rules, Automation, Presentation, Contracts, Application,
    CommandBus, or QueryBus. It never lets an exception from any internal
    step escape `run()` — every failure becomes a
    `OperationResult(success=False, reason=...)` instead.

    `operation_history_service` defaults to a fresh OperationHistoryService
    when not given, so existing single-argument construction
    (`OperationsCoordinator(operations_engine)`) keeps working unchanged —
    OperationHistoryService has no dependency of its own, so this default
    is never a real wiring decision, only convenience.
    """

    def __init__(
        self,
        operations_engine: OperationsEngine,
        operation_history_service: OperationHistoryService | None = None,
    ) -> None:
        self._operations_engine = operations_engine
        self._operation_history_service = operation_history_service or OperationHistoryService()

    def run(self, context: OperationContext) -> OperationResult:
        started_at = time.perf_counter()
        history: OperationHistory | None = None

        try:
            operation = self._operations_engine.create_operation(
                context.operation_name, metadata=context.metadata
            )
            history = self._operation_history_service.create(operation)

            operation = self._operations_engine.start_operation(operation.id)
            history = self._operation_history_service.record_started(history)

            operation = self._operations_engine.finish_operation(operation.id)
            history = self._operation_history_service.record_finished(history)

            status = self._operations_engine.operation_repository.get_status(operation.id)

            return OperationResult(
                success=True,
                operation=operation,
                status=status,
                reason=None,
                execution_time=time.perf_counter() - started_at,
                history=history,
            )
        except Exception as exc:
            if history is not None:
                history = self._operation_history_service.record_failed(history, reason=str(exc))
            return OperationResult(
                success=False,
                operation=None,
                status=None,
                reason=str(exc),
                execution_time=time.perf_counter() - started_at,
                history=history,
            )
