from datetime import datetime, timezone

from app.operations.models.operation import Operation
from app.operations.models.operation_status import OperationStatus
from app.operations.repositories.operation_repository import OperationRepository

_T0 = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


def test_save_and_get_operation():
    repository = OperationRepository()
    operation = Operation(name="Sync inventory")

    repository.save_operation(operation)

    assert repository.get_operation(operation.id) is operation


def test_get_operation_returns_none_when_absent():
    repository = OperationRepository()

    assert repository.get_operation(Operation(name="x").id) is None


def test_list_operations_returns_every_saved_operation():
    repository = OperationRepository()
    first = Operation(name="First")
    second = Operation(name="Second")

    repository.save_operation(first)
    repository.save_operation(second)

    assert {o.id for o in repository.list_operations()} == {first.id, second.id}


def test_list_operations_is_empty_by_default():
    repository = OperationRepository()

    assert repository.list_operations() == []


def test_save_and_get_status():
    repository = OperationRepository()
    operation = Operation(name="Sync inventory")
    status = OperationStatus(
        operation_id=operation.id, running=True, progress=50.0, message=None, updated_at=_T0
    )

    repository.save_status(status)

    assert repository.get_status(operation.id) is status


def test_get_status_returns_none_when_absent():
    repository = OperationRepository()

    assert repository.get_status(Operation(name="x").id) is None


def test_saving_a_new_status_replaces_the_previous_one():
    repository = OperationRepository()
    operation = Operation(name="Sync inventory")
    first_status = OperationStatus(
        operation_id=operation.id, running=True, progress=10.0, message=None, updated_at=_T0
    )
    second_status = OperationStatus(
        operation_id=operation.id, running=True, progress=90.0, message=None, updated_at=_T0
    )

    repository.save_status(first_status)
    repository.save_status(second_status)

    assert repository.get_status(operation.id) is second_status
