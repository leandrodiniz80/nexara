from app.observability.engine.observability_engine import ObservabilityEngine
from app.observability.models.execution_step import ExecutionStatus
from app.observability.models.execution_trace import ExecutionTrace
from app.observability.operations.operation_trace_service import OperationTraceService
from app.observability.tracing.trace_context import TraceContext
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory

_EXECUTION_TYPE = "operation"
_COMPONENT = "operations"


class ObservabilityOperationsService:
    """Adapts Operations' history/result into ObservabilityEngine's
    existing public API — no new method was added to ObservabilityEngine
    to make this possible, and it is never altered.

    It knows exclusively ObservabilityEngine and OperationTraceService:
    `record()` first asks OperationTraceService to build the OperationTrace
    for an already-finished OperationHistory/OperationResult, then
    translates that trace's events into a sequence of ObservabilityEngine
    calls it already supports (`start_trace()`, `register_step()` per
    event, `finish_trace()`) — the same start/step/finish shape every other
    consumer of ObservabilityEngine already uses, just fed from Operations
    instead of a Mission/Task/Job.
    """

    def __init__(
        self,
        observability_engine: ObservabilityEngine,
        operation_trace_service: OperationTraceService,
    ) -> None:
        self._observability_engine = observability_engine
        self._operation_trace_service = operation_trace_service

    def record(self, history: OperationHistory, result: OperationResult) -> ExecutionTrace:
        operation_trace = self._operation_trace_service.build_trace(history, result)

        context = TraceContext(metadata=dict(operation_trace.metadata))
        execution_trace = self._observability_engine.start_trace(context, _EXECUTION_TYPE)

        for event in operation_trace.events:
            execution_trace = self._observability_engine.register_step(
                execution_trace,
                step_name=event.event_type,
                component=_COMPONENT,
                started_at=event.timestamp,
                finished_at=event.timestamp,
                status=ExecutionStatus.SUCCESS,
            )

        final_status = (
            ExecutionStatus.SUCCESS if operation_trace.success else ExecutionStatus.FAILED
        )
        return self._observability_engine.finish_trace(execution_trace, status=final_status)
