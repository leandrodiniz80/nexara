import uuid

from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution


class ExecutionRepository:
    """In-memory store of every Execution — no database, same reasoning as every
    other in-memory repository in this codebase: no migration was requested for
    this module.
    """

    def __init__(self) -> None:
        self._executions: dict[uuid.UUID, Execution] = {}

    def save_execution(self, execution: Execution) -> Execution:
        self._executions[execution.id] = execution
        return execution

    def get_execution(self, execution_id: uuid.UUID) -> Execution | None:
        return self._executions.get(execution_id)

    def list_executions(
        self,
        *,
        execution_type: ExecutionType | None = None,
        status: ExecutionStatus | None = None,
    ) -> list[Execution]:
        executions = list(self._executions.values())
        if execution_type is not None:
            executions = [e for e in executions if e.execution_type == execution_type]
        if status is not None:
            executions = [e for e in executions if e.status == status]
        return executions
