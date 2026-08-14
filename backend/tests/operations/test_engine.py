import inspect

import pytest
from pydantic import ValidationError

from app.operations.engine import operations_engine as operations_engine_module
from app.operations.engine.operations_engine import OperationsEngine
from app.operations.exceptions.operations_exceptions import OperationNotFoundError
from app.operations.models import enums as enums_module
from app.operations.models import operation as operation_module
from app.operations.models import operation_status as operation_status_module
from app.operations.models import operation_summary as operation_summary_module
from app.operations.models.enums import OperationState
from app.operations.models.operation import Operation
from app.operations.repositories import operation_repository as operation_repository_module
from app.operations.repositories.operation_repository import OperationRepository

_MODULES = (
    operations_engine_module,
    enums_module,
    operation_module,
    operation_status_module,
    operation_summary_module,
    operation_repository_module,
)


def _engine() -> OperationsEngine:
    return OperationsEngine(OperationRepository())


def test_criacao_returns_a_pending_operation():
    engine = _engine()

    operation = engine.create_operation("Sync inventory", metadata={"source": "test"})

    assert isinstance(operation, Operation)
    assert operation.name == "Sync inventory"
    assert operation.status == OperationState.PENDING
    assert operation.started_at is None
    assert operation.finished_at is None
    assert operation.metadata == {"source": "test"}


def test_start_marks_the_operation_as_running():
    engine = _engine()
    operation = engine.create_operation("Sync inventory")

    started = engine.start_operation(operation.id)

    assert started.status == OperationState.RUNNING
    assert started.started_at is not None
    assert started.finished_at is None
    status = engine.operation_repository.get_status(operation.id)
    assert status.running is True
    assert status.progress == 0.0


def test_start_raises_when_operation_is_unknown():
    engine = _engine()

    with pytest.raises(OperationNotFoundError):
        engine.start_operation(Operation(name="x").id)


def test_finish_marks_the_operation_as_finished():
    engine = _engine()
    operation = engine.create_operation("Sync inventory")
    engine.start_operation(operation.id)

    finished = engine.finish_operation(operation.id)

    assert finished.status == OperationState.FINISHED
    assert finished.finished_at is not None
    status = engine.operation_repository.get_status(operation.id)
    assert status.running is False
    assert status.progress == 100.0


def test_finish_raises_when_operation_is_unknown():
    engine = _engine()

    with pytest.raises(OperationNotFoundError):
        engine.finish_operation(Operation(name="x").id)


def test_fail_marks_the_operation_as_failed_with_a_message():
    engine = _engine()
    operation = engine.create_operation("Sync inventory")
    engine.start_operation(operation.id)

    failed = engine.fail_operation(operation.id, message="Timeout while syncing.")

    assert failed.status == OperationState.FAILED
    assert failed.finished_at is not None
    status = engine.operation_repository.get_status(operation.id)
    assert status.running is False
    assert status.message == "Timeout while syncing."


def test_fail_preserves_the_last_known_progress():
    engine = _engine()
    operation = engine.create_operation("Sync inventory")
    engine.start_operation(operation.id)
    engine.operation_repository.save_status(
        engine.operation_repository.get_status(operation.id).model_copy(
            update={"progress": 42.0}
        )
    )

    engine.fail_operation(operation.id)

    status = engine.operation_repository.get_status(operation.id)
    assert status.progress == 42.0


def test_fail_raises_when_operation_is_unknown():
    engine = _engine()

    with pytest.raises(OperationNotFoundError):
        engine.fail_operation(Operation(name="x").id)


def test_list_operations_reflects_every_created_operation():
    engine = _engine()
    first = engine.create_operation("First")
    second = engine.create_operation("Second")

    listed = engine.list_operations()

    assert {o.id for o in listed} == {first.id, second.id}


def test_summary_counts_operations_by_state():
    engine = _engine()
    running = engine.create_operation("Running")
    finished = engine.create_operation("Finished")
    failed = engine.create_operation("Failed")
    pending = engine.create_operation("Pending")
    engine.start_operation(running.id)
    engine.start_operation(finished.id)
    engine.finish_operation(finished.id)
    engine.start_operation(failed.id)
    engine.fail_operation(failed.id)

    summary = engine.summary()

    assert summary.total_operations == 4
    assert summary.running_operations == 1
    assert summary.finished_operations == 1
    assert summary.failed_operations == 1
    assert pending.status == OperationState.PENDING


def test_injecao_uses_exactly_the_repository_provided():
    repository = OperationRepository()

    engine = OperationsEngine(repository)

    assert engine.operation_repository is repository


def test_imutabilidade_rejects_attribute_assignment():
    engine = _engine()
    operation = engine.create_operation("Sync inventory")
    started = engine.start_operation(operation.id)
    status = engine.operation_repository.get_status(operation.id)
    summary = engine.summary()

    with pytest.raises(ValidationError):
        started.status = OperationState.FAILED

    with pytest.raises(ValidationError):
        status.running = False

    with pytest.raises(ValidationError):
        summary.total_operations = 99


def test_zero_dependencias_externas():
    forbidden = (
        "app.crm",
        "app.runtime",
        "app.workflows",
        "app.decision",
        "app.business_rules",
        "app.presentation",
        "app.contracts",
        "app.application",
        "app.bootstrap",
        "app.platform",
        "app.config",
        "app.interface",
        "app.automation",
    )
    for module in _MODULES:
        source = inspect.getsource(module)
        for forbidden_import in forbidden:
            assert forbidden_import not in source
