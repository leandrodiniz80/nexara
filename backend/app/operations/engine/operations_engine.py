import uuid
from datetime import datetime, timezone
from typing import Any

from app.operations.exceptions.operations_exceptions import OperationNotFoundError
from app.operations.models.enums import OperationState
from app.operations.models.operation import Operation
from app.operations.models.operation_status import OperationStatus
from app.operations.models.operation_summary import OperationSummary
from app.operations.repositories.operation_repository import OperationRepository

_STARTED_PROGRESS = 0.0
_FINISHED_PROGRESS = 100.0


class OperationsEngine:
    """Models the platform's operational core — creating, tracking, and
    summarizing Operations. It coordinates nothing outside this module:
    no Runtime, no Workflow, no CRM, no Decision, no Business Rules, no
    Application, no Presentation. It is fully self-contained, backed by an
    in-memory OperationRepository.
    """

    def __init__(self, operation_repository: OperationRepository) -> None:
        self.operation_repository = operation_repository

    def create_operation(self, name: str, *, metadata: dict[str, Any] | None = None) -> Operation:
        operation = Operation(name=name, metadata=metadata or {})
        return self.operation_repository.save_operation(operation)

    def start_operation(self, operation_id: uuid.UUID) -> Operation:
        operation = self._get_operation(operation_id)
        now = datetime.now(timezone.utc)

        self.operation_repository.save_status(
            OperationStatus(
                operation_id=operation_id,
                running=True,
                progress=_STARTED_PROGRESS,
                message=None,
                updated_at=now,
            )
        )
        started = operation.model_copy(
            update={"started_at": now, "status": OperationState.RUNNING}
        )
        return self.operation_repository.save_operation(started)

    def finish_operation(self, operation_id: uuid.UUID) -> Operation:
        operation = self._get_operation(operation_id)
        now = datetime.now(timezone.utc)

        self.operation_repository.save_status(
            OperationStatus(
                operation_id=operation_id,
                running=False,
                progress=_FINISHED_PROGRESS,
                message=None,
                updated_at=now,
            )
        )
        finished = operation.model_copy(
            update={"finished_at": now, "status": OperationState.FINISHED}
        )
        return self.operation_repository.save_operation(finished)

    def fail_operation(self, operation_id: uuid.UUID, *, message: str | None = None) -> Operation:
        operation = self._get_operation(operation_id)
        now = datetime.now(timezone.utc)

        previous_status = self.operation_repository.get_status(operation_id)
        progress = previous_status.progress if previous_status is not None else _STARTED_PROGRESS

        self.operation_repository.save_status(
            OperationStatus(
                operation_id=operation_id,
                running=False,
                progress=progress,
                message=message,
                updated_at=now,
            )
        )
        failed = operation.model_copy(update={"finished_at": now, "status": OperationState.FAILED})
        return self.operation_repository.save_operation(failed)

    def list_operations(self) -> list[Operation]:
        return self.operation_repository.list_operations()

    def summary(self) -> OperationSummary:
        operations = self.operation_repository.list_operations()
        running = sum(1 for o in operations if o.status == OperationState.RUNNING)
        finished = sum(1 for o in operations if o.status == OperationState.FINISHED)
        failed = sum(1 for o in operations if o.status == OperationState.FAILED)

        return OperationSummary(
            total_operations=len(operations),
            running_operations=running,
            finished_operations=finished,
            failed_operations=failed,
        )

    def _get_operation(self, operation_id: uuid.UUID) -> Operation:
        operation = self.operation_repository.get_operation(operation_id)
        if operation is None:
            raise OperationNotFoundError(operation_id)
        return operation
