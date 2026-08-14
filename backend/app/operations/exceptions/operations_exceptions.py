import uuid

from app.operations.exceptions.base import OperationsError


class OperationNotFoundError(OperationsError):
    def __init__(self, operation_id: uuid.UUID) -> None:
        self.operation_id = operation_id
        super().__init__(f"No Operation found with id {operation_id}.")
