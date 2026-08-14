import uuid

from app.automation.models.automation_execution import AutomationExecution
from app.automation.models.enums import AutomationStatus


class AutomationRepository:
    """In-memory store of every AutomationExecution — no database, same reasoning
    as every other in-memory repository in this codebase. Stores *executions*
    (runtime firings); Automation *definitions* live in AutomationRegistry, the
    same split Workflow/WorkflowRepository already established one layer down.
    """

    def __init__(self) -> None:
        self._executions: dict[uuid.UUID, AutomationExecution] = {}

    def save_execution(self, execution: AutomationExecution) -> AutomationExecution:
        self._executions[execution.execution_id] = execution
        return execution

    def get_execution(self, execution_id: uuid.UUID) -> AutomationExecution | None:
        return self._executions.get(execution_id)

    def list_executions(
        self,
        *,
        automation_id: uuid.UUID | None = None,
        status: AutomationStatus | None = None,
    ) -> list[AutomationExecution]:
        executions = list(self._executions.values())
        if automation_id is not None:
            executions = [e for e in executions if e.automation_id == automation_id]
        if status is not None:
            executions = [e for e in executions if e.status == status]
        return executions
