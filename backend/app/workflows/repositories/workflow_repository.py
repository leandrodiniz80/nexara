import uuid

from app.workflows.models.enums import WorkflowStatus
from app.workflows.models.workflow_execution import WorkflowExecution


class WorkflowRepository:
    """In-memory store of every WorkflowExecution — no database, same reasoning as
    every other in-memory repository in this codebase (JobRepository,
    OutreachAssetRepository): no migration was requested for this module. Stores
    *executions* (runtime state); Workflow *definitions* live in WorkflowRegistry,
    the same split as AssetTemplate (definition, in TemplateRepository) vs
    OutreachAsset (runtime instance, in OutreachAssetRepository).
    """

    def __init__(self) -> None:
        self._executions: dict[uuid.UUID, WorkflowExecution] = {}

    def save_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        self._executions[execution.execution_id] = execution
        return execution

    def get_execution(self, execution_id: uuid.UUID) -> WorkflowExecution | None:
        return self._executions.get(execution_id)

    def list_executions(
        self,
        *,
        workflow_id: uuid.UUID | None = None,
        status: WorkflowStatus | None = None,
    ) -> list[WorkflowExecution]:
        executions = list(self._executions.values())
        if workflow_id is not None:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        if status is not None:
            executions = [e for e in executions if e.status == status]
        return executions
