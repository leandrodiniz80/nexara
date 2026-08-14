import uuid
from typing import Any

from app.application.tasks.context.task_context import TaskContext
from app.runtime.engine.runtime_engine import RuntimeEngine
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult
from app.workflows.schemas.workflow_request import WorkflowRequest

DEFAULT_PROSPECTING_WORKFLOW_NAME = "Prospecting Workflow"


class ExecutionService:
    """The Application layer's single facade over Runtime — the only place in
    app.application that still knows WorkflowRequest, TaskContext, and
    ExecutionContext exist. Every high-level command it exposes translates
    its own plain parameters into those three objects and delegates
    immediately to RuntimeEngine.execute_workflow(), returning its
    ExecutionResult completely untouched.

    It contains no business rule and makes no decision of its own — that is,
    and remains, Runtime's job. This class only assembles the objects
    Runtime's existing public API already expects; it never raises anything
    of its own, and never catches what RuntimeEngine raises either, so a
    genuine Runtime failure propagates to the caller exactly as it always has.
    """

    def __init__(self, runtime_engine: RuntimeEngine) -> None:
        self.runtime_engine = runtime_engine

    async def execute_prospecting(
        self,
        *,
        workflow_name: str = DEFAULT_PROSPECTING_WORKFLOW_NAME,
        mission_id: uuid.UUID | None = None,
        variables: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        execution_context = ExecutionContext(
            mission_id=mission_id,
            workflow_request=WorkflowRequest(
                workflow_name=workflow_name,
                context=TaskContext(mission_id=mission_id, variables=dict(variables or {})),
            ),
        )
        return await self.runtime_engine.execute_workflow(execution_context)
