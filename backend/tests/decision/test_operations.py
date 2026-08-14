import inspect
import uuid
from datetime import datetime, timedelta, timezone

from app.decision.engine.decision_engine_factory import build_default_decision_engine
from app.decision.models.decision_result import DecisionResult
from app.decision.operations import decision_operations_service, operation_decision_service
from app.decision.operations.decision_operations_service import DecisionOperationsService
from app.decision.operations.decision_operations_service_factory import (
    build_default_decision_operations_service,
)
from app.decision.operations.operation_decision_context import OperationDecisionContext
from app.decision.operations.operation_decision_service import OperationDecisionService
from app.decision.operations.operation_decision_service_factory import (
    build_default_operation_decision_service,
)
from app.observability.operations.operation_trace import OperationTrace
from app.operations.coordinator.operation_result import OperationResult
from app.operations.history.operation_history import OperationHistory
from app.operations.history.operation_history_event import OperationHistoryEvent
from app.operations.models.enums import OperationState
from app.operations.models.operation import Operation
from app.operations.models.operation_status import OperationStatus

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(minutes=1)
_T2 = _T0 + timedelta(minutes=2)


def _operation() -> Operation:
    return Operation(
        name="Sync inventory",
        started_at=_T0,
        finished_at=_T2,
        status=OperationState.FINISHED,
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


def _result(operation: Operation, history: OperationHistory, *, success: bool) -> OperationResult:
    status = OperationStatus(
        operation_id=operation.id, running=False, progress=100.0, updated_at=_T2
    )
    return OperationResult(
        success=success,
        operation=operation if success else None,
        status=status if success else None,
        reason=None if success else "Timeout while syncing.",
        execution_time=1.5,
        history=history,
    )


def _trace(history: OperationHistory, result: OperationResult) -> OperationTrace:
    return OperationTrace(
        operation_id=history.operation_id,
        started_at=history.events[0].timestamp,
        finished_at=history.events[-1].timestamp,
        duration=result.execution_time,
        success=result.success,
        events=history.events,
    )


class _CountingDecisionEngine:
    def __init__(self) -> None:
        self._real = build_default_decision_engine()
        self.calls = 0

    def decide(self, decision_type, context, *, priority: int = 0):
        self.calls += 1
        return self._real.decide(decision_type, context, priority=priority)


def test_context_criado():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)
    service = OperationDecisionService()

    context = service.build_context(history, result, trace)

    assert isinstance(context, OperationDecisionContext)


def test_history_preservado():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)
    service = OperationDecisionService()

    context = service.build_context(history, result, trace)

    assert context.operation_history is history


def test_result_preservado():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)
    service = OperationDecisionService()

    context = service.build_context(history, result, trace)

    assert context.operation_result is result


def test_trace_preservado():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)
    service = OperationDecisionService()

    context = service.build_context(history, result, trace)

    assert context.operation_trace is trace


def test_build_default_operation_decision_service_returns_a_usable_service():
    service = build_default_operation_decision_service()
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)

    assert isinstance(service, OperationDecisionService)
    context = service.build_context(history, result, trace)
    assert isinstance(context, OperationDecisionContext)


def test_evaluate_returns_a_decision_result_favoring_proceed_on_success():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)
    service = DecisionOperationsService(
        build_default_decision_engine(), OperationDecisionService()
    )

    decision_result = service.evaluate(history, result, trace)

    assert isinstance(decision_result, DecisionResult)
    assert decision_result.success is True
    assert decision_result.selected_option.name == "proceed"


def test_evaluate_favors_retry_on_operational_failure():
    operation = _operation()
    history = _history(operation.id, ["created", "failed"])
    result = _result(operation, history, success=False)
    trace = _trace(history, result)
    service = DecisionOperationsService(
        build_default_decision_engine(), OperationDecisionService()
    )

    decision_result = service.evaluate(history, result, trace)

    assert decision_result.success is True
    assert decision_result.selected_option.name == "retry"


def test_decision_engine_chamado_exatamente_uma_vez():
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)
    decision_engine = _CountingDecisionEngine()
    service = DecisionOperationsService(decision_engine, OperationDecisionService())

    service.evaluate(history, result, trace)

    assert decision_engine.calls == 1


def test_injecao_uses_exactly_the_collaborators_provided():
    decision_engine = build_default_decision_engine()
    operation_decision_svc = OperationDecisionService()

    service = DecisionOperationsService(decision_engine, operation_decision_svc)

    assert service._decision_engine is decision_engine
    assert service._operation_decision_service is operation_decision_svc


def test_build_default_decision_operations_service_returns_a_usable_service():
    service = build_default_decision_operations_service()
    operation = _operation()
    history = _history(operation.id, ["created", "started", "finished"])
    result = _result(operation, history, success=True)
    trace = _trace(history, result)

    assert isinstance(service, DecisionOperationsService)
    decision_result = service.evaluate(history, result, trace)
    assert isinstance(decision_result, DecisionResult)


def test_nenhum_import_de_runtime():
    for module in (operation_decision_service, decision_operations_service):
        source = inspect.getsource(module)
        assert "app.runtime" not in source


def test_nenhum_import_de_crm():
    for module in (operation_decision_service, decision_operations_service):
        source = inspect.getsource(module)
        assert "app.crm" not in source


def test_nenhum_import_de_workflow():
    for module in (operation_decision_service, decision_operations_service):
        source = inspect.getsource(module)
        assert "app.workflows" not in source


def test_nenhum_import_de_application():
    for module in (operation_decision_service, decision_operations_service):
        source = inspect.getsource(module)
        assert "app.application" not in source


def test_nenhum_import_de_presentation():
    for module in (operation_decision_service, decision_operations_service):
        source = inspect.getsource(module)
        assert "app.presentation" not in source
