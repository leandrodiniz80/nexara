import inspect

import pytest
from pydantic import ValidationError

from app.operations.coordinator import operations_coordinator
from app.operations.coordinator.operation_context import OperationContext
from app.operations.coordinator.operation_result import OperationResult
from app.operations.coordinator.operations_coordinator import OperationsCoordinator
from app.operations.coordinator.operations_coordinator_factory import (
    build_default_operations_coordinator,
)
from app.operations.history.operation_history import OperationHistory
from app.operations.history.operation_history_service import OperationHistoryService
from app.operations.models.enums import OperationState
from app.operations.services.operations_engine_factory import build_default_operations_engine


class _BrokenOperationsEngine:
    def create_operation(self, name, *, metadata=None):
        raise RuntimeError("Something went wrong while creating the operation.")


class _EngineThatFailsOnStart:
    """Succeeds at create_operation() but fails at start_operation() — used
    to exercise the case where a history already exists by the time the
    failure happens."""

    def __init__(self) -> None:
        self._real = build_default_operations_engine()

    def create_operation(self, name, *, metadata=None):
        return self._real.create_operation(name, metadata=metadata)

    def start_operation(self, operation_id):
        raise RuntimeError("Boom during start.")


class _CountingOperationHistoryService:
    def __init__(self) -> None:
        self._real = OperationHistoryService()
        self.create_calls = 0
        self.started_calls = 0
        self.finished_calls = 0
        self.failed_calls = 0

    def create(self, operation, *, now=None):
        self.create_calls += 1
        return self._real.create(operation, now=now)

    def record_started(self, history, *, now=None):
        self.started_calls += 1
        return self._real.record_started(history, now=now)

    def record_finished(self, history, *, now=None):
        self.finished_calls += 1
        return self._real.record_finished(history, now=now)

    def record_failed(self, history, *, reason=None, now=None):
        self.failed_calls += 1
        return self._real.record_failed(history, reason=reason, now=now)


def test_run_completes_the_full_lifecycle_on_success():
    coordinator = OperationsCoordinator(build_default_operations_engine())
    context = OperationContext(operation_name="Sync inventory", metadata={"source": "test"})

    result = coordinator.run(context)

    assert isinstance(result, OperationResult)
    assert result.success is True
    assert result.reason is None
    assert result.operation.name == "Sync inventory"
    assert result.operation.status == OperationState.FINISHED
    assert result.operation.started_at is not None
    assert result.operation.finished_at is not None
    assert result.status.running is False
    assert result.status.progress == 100.0


def test_run_success_preserves_the_contexts_metadata():
    coordinator = OperationsCoordinator(build_default_operations_engine())
    context = OperationContext(operation_name="Sync inventory", metadata={"batch": 7})

    result = coordinator.run(context)

    assert result.operation.metadata == {"batch": 7}


def test_run_failure_never_propagates_the_exception():
    coordinator = OperationsCoordinator(_BrokenOperationsEngine())
    context = OperationContext(operation_name="Sync inventory")

    result = coordinator.run(context)

    assert isinstance(result, OperationResult)
    assert result.success is False
    assert result.operation is None
    assert result.status is None
    assert result.reason == "Something went wrong while creating the operation."


def test_run_failure_still_reports_a_non_negative_execution_time():
    coordinator = OperationsCoordinator(_BrokenOperationsEngine())
    context = OperationContext(operation_name="Sync inventory")

    result = coordinator.run(context)

    assert isinstance(result.execution_time, float)
    assert result.execution_time >= 0.0


def test_injecao_uses_exactly_the_engine_provided():
    engine = build_default_operations_engine()

    coordinator = OperationsCoordinator(engine)

    assert coordinator._operations_engine is engine


def test_build_default_operations_coordinator_returns_a_usable_coordinator():
    coordinator = build_default_operations_coordinator()
    context = OperationContext(operation_name="Sync inventory")

    assert isinstance(coordinator, OperationsCoordinator)
    result = coordinator.run(context)
    assert result.success is True


def test_build_default_operations_coordinator_uses_a_fresh_repository():
    first = build_default_operations_coordinator()
    first.run(OperationContext(operation_name="First"))

    second = build_default_operations_coordinator()

    assert second._operations_engine.list_operations() == []


def test_imutabilidade_rejects_attribute_assignment():
    coordinator = OperationsCoordinator(build_default_operations_engine())
    context = OperationContext(operation_name="Sync inventory")
    result = coordinator.run(context)

    with pytest.raises(ValidationError):
        context.operation_name = "altered"

    with pytest.raises(ValidationError):
        result.success = False


def test_run_success_carries_the_full_history():
    coordinator = OperationsCoordinator(build_default_operations_engine())
    context = OperationContext(operation_name="Sync inventory")

    result = coordinator.run(context)

    assert isinstance(result.history, OperationHistory)
    assert [e.event_type for e in result.history.events] == ["created", "started", "finished"]


def test_run_failure_before_history_exists_leaves_history_none():
    coordinator = OperationsCoordinator(_BrokenOperationsEngine())
    context = OperationContext(operation_name="Sync inventory")

    result = coordinator.run(context)

    assert result.history is None


def test_run_failure_after_creation_still_carries_a_partial_history_with_failed():
    coordinator = OperationsCoordinator(_EngineThatFailsOnStart())
    context = OperationContext(operation_name="Sync inventory")

    result = coordinator.run(context)

    assert result.success is False
    assert isinstance(result.history, OperationHistory)
    assert [e.event_type for e in result.history.events] == ["created", "failed"]
    assert result.history.events[-1].message == "Boom during start."


def test_coordinator_chama_history_exatamente_uma_vez_por_etapa_no_sucesso():
    history_service = _CountingOperationHistoryService()
    coordinator = OperationsCoordinator(build_default_operations_engine(), history_service)
    context = OperationContext(operation_name="Sync inventory")

    coordinator.run(context)

    assert history_service.create_calls == 1
    assert history_service.started_calls == 1
    assert history_service.finished_calls == 1
    assert history_service.failed_calls == 0


def test_coordinator_chama_history_exatamente_uma_vez_por_etapa_na_falha():
    history_service = _CountingOperationHistoryService()
    coordinator = OperationsCoordinator(_EngineThatFailsOnStart(), history_service)
    context = OperationContext(operation_name="Sync inventory")

    coordinator.run(context)

    assert history_service.create_calls == 1
    assert history_service.started_calls == 0
    assert history_service.finished_calls == 0
    assert history_service.failed_calls == 1


def test_injecao_uses_exactly_the_history_service_provided():
    engine = build_default_operations_engine()
    history_service = _CountingOperationHistoryService()

    coordinator = OperationsCoordinator(engine, history_service)

    assert coordinator._operation_history_service is history_service


def test_operation_history_service_defaults_when_not_provided():
    coordinator = OperationsCoordinator(build_default_operations_engine())

    assert isinstance(coordinator._operation_history_service, OperationHistoryService)


def test_build_default_operations_coordinator_wires_a_working_history_service():
    coordinator = build_default_operations_coordinator()

    assert isinstance(coordinator._operation_history_service, OperationHistoryService)


def test_nenhum_import_de_crm():
    source = inspect.getsource(operations_coordinator)
    assert "app.crm" not in source


def test_nenhum_import_de_runtime():
    source = inspect.getsource(operations_coordinator)
    assert "app.runtime" not in source


def test_nenhum_import_de_workflow():
    source = inspect.getsource(operations_coordinator)
    assert "app.workflows" not in source


def test_nenhum_import_de_presentation():
    source = inspect.getsource(operations_coordinator)
    assert "app.presentation" not in source


def test_nenhum_import_de_contracts():
    source = inspect.getsource(operations_coordinator)
    assert "app.contracts" not in source
