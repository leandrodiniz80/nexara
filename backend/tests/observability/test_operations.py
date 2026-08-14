import inspect
import uuid
from datetime import datetime, timedelta, timezone

from app.observability.models.execution_step import ExecutionStatus
from app.observability.models.execution_trace import ExecutionTrace
from app.observability.operations import observability_operations_service, operation_trace_service
from app.observability.operations.observability_operations_service import (
    ObservabilityOperationsService,
)
from app.observability.operations.observability_operations_service_factory import (
    build_default_observability_operations_service,
)
from app.observability.operations.operation_trace import OperationTrace
from app.observability.operations.operation_trace_service import OperationTraceService
from app.observability.operations.operation_trace_service_factory import (
    build_default_operation_trace_service,
)
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory
from app.operations.history.operation_history_event import OperationHistoryEvent
from app.operations.models.enums import OperationState
from app.operations.models.operation import Operation
from app.operations.models.operation_status import OperationStatus

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(minutes=1)
_T2 = _T0 + timedelta(minutes=2)


def _operation(*, metadata: dict | None = None) -> Operation:
    return Operation(
        name="Sync inventory",
        started_at=_T0,
        finished_at=_T2,
        status=OperationState.FINISHED,
        metadata=metadata or {},
    )


def _history(operation_id: uuid.UUID, event_types: list[str]) -> OperationHistory:
    timestamps = [_T0, _T1, _T2]
    events = tuple(
        OperationHistoryEvent(
            event_type=event_type, timestamp=timestamps[i], message=f"{event_type}."
        )
        for i, event_type in enumerate(event_types)
    )
    return OperationHistory(operation_id=operation_id, events=events)


def _success_result(operation: Operation, history: OperationHistory) -> OperationResult:
    status = OperationStatus(
        operation_id=operation.id, running=False, progress=100.0, updated_at=_T2
    )
    return OperationResult(
        success=True,
        operation=operation,
        status=status,
        reason=None,
        execution_time=1.5,
        history=history,
    )


def _failure_result(history: OperationHistory) -> OperationResult:
    return OperationResult(
        success=False,
        operation=None,
        status=None,
        reason="Timeout while syncing.",
        execution_time=0.5,
        history=history,
    )


def test_trace_criado():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    service = OperationTraceService()

    trace = service.build_trace(history, _success_result(operation, history))

    assert isinstance(trace, OperationTrace)
    assert trace.operation_id == operation.id


def test_eventos_preservados():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    service = OperationTraceService()

    trace = service.build_trace(history, _success_result(operation, history))

    assert trace.events == history.events
    assert [e.event_type for e in trace.events] == ["created", "started", "finished"]


def test_duracao_correta():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _success_result(operation, history)
    service = OperationTraceService()

    trace = service.build_trace(history, result)

    assert trace.duration == result.execution_time
    assert trace.started_at == _T0
    assert trace.finished_at == _T2


def test_sucesso():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    service = OperationTraceService()

    trace = service.build_trace(history, _success_result(operation, history))

    assert trace.success is True


def test_falha():
    operation = _operation()
    history = _history(operation.id, ["created", "failed"])
    service = OperationTraceService()

    trace = service.build_trace(history, _failure_result(history))

    assert trace.success is False
    assert [e.event_type for e in trace.events] == ["created", "failed"]


def test_never_alters_the_given_history_or_result():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _success_result(operation, history)
    service = OperationTraceService()

    service.build_trace(history, result)

    assert len(history.events) == 3
    assert result.success is True


def test_build_default_operation_trace_service_returns_a_usable_service():
    service = build_default_operation_trace_service()
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])

    assert isinstance(service, OperationTraceService)
    trace = service.build_trace(history, _success_result(operation, history))
    assert isinstance(trace, OperationTrace)


def test_record_delegates_to_observability_engine_and_returns_an_execution_trace():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _success_result(operation, history)
    service = ObservabilityOperationsService(
        build_default_observability_engine(), OperationTraceService()
    )

    execution_trace = service.record(history, result)

    assert isinstance(execution_trace, ExecutionTrace)
    assert execution_trace.status == ExecutionStatus.SUCCESS
    assert [s.step_name for s in execution_trace.steps] == ["created", "started", "finished"]


def test_record_marks_the_execution_trace_as_failed_on_operational_failure():
    operation = _operation()
    history = _history(operation.id, ["created", "failed"])
    result = _failure_result(history)
    service = ObservabilityOperationsService(
        build_default_observability_engine(), OperationTraceService()
    )

    execution_trace = service.record(history, result)

    assert execution_trace.status == ExecutionStatus.FAILED


def test_injecao_uses_exactly_the_collaborators_provided():
    observability_engine = build_default_observability_engine()
    operation_trace_svc = OperationTraceService()

    service = ObservabilityOperationsService(observability_engine, operation_trace_svc)

    assert service._observability_engine is observability_engine
    assert service._operation_trace_service is operation_trace_svc


def test_build_default_observability_operations_service_returns_a_usable_service():
    service = build_default_observability_operations_service()
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _success_result(operation, history)

    assert isinstance(service, ObservabilityOperationsService)
    execution_trace = service.record(history, result)
    assert isinstance(execution_trace, ExecutionTrace)


def test_nenhum_import_de_runtime():
    for module in (operation_trace_service, observability_operations_service):
        source = inspect.getsource(module)
        assert "app.runtime" not in source


def test_nenhum_import_de_crm():
    for module in (operation_trace_service, observability_operations_service):
        source = inspect.getsource(module)
        assert "app.crm" not in source


def test_nenhum_import_de_workflow():
    for module in (operation_trace_service, observability_operations_service):
        source = inspect.getsource(module)
        assert "app.workflows" not in source


def test_nenhum_import_de_application():
    for module in (operation_trace_service, observability_operations_service):
        source = inspect.getsource(module)
        assert "app.application" not in source


def test_nenhum_import_de_presentation():
    for module in (operation_trace_service, observability_operations_service):
        source = inspect.getsource(module)
        assert "app.presentation" not in source
