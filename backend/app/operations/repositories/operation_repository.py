import uuid

from app.operations.models.operation import Operation
from app.operations.models.operation_status import OperationStatus


class OperationRepository:
    """In-memory store of every Operation and its latest OperationStatus."""

    def __init__(self) -> None:
        self._operations: dict[uuid.UUID, Operation] = {}
        self._statuses: dict[uuid.UUID, OperationStatus] = {}

    def save_operation(self, operation: Operation) -> Operation:
        self._operations[operation.id] = operation
        return operation

    def get_operation(self, operation_id: uuid.UUID) -> Operation | None:
        return self._operations.get(operation_id)

    def list_operations(self) -> list[Operation]:
        return list(self._operations.values())

    def save_status(self, status: OperationStatus) -> OperationStatus:
        self._statuses[status.operation_id] = status
        return status

    def get_status(self, operation_id: uuid.UUID) -> OperationStatus | None:
        return self._statuses.get(operation_id)
