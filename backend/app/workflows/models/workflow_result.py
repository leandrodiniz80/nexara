from typing import Any

from pydantic import BaseModel, Field

from app.workflows.models.workflow_execution import WorkflowExecution


class WorkflowResult(BaseModel):
    """What every WorkflowEngine.execute_workflow()/resume()/retry() call returns
    — the same "always a result, never a raised exception past this boundary" shape
    as TaskResult/ApplicationServiceResult one layer down. `success` is True only
    when the execution reached COMPLETED with zero failed_steps — a workflow that
    finished via tolerated failures (continue_on_error=True) still reports
    success=False, even though `execution.status` is COMPLETED, so a caller can
    tell "it finished running" apart from "everything actually worked".
    """

    success: bool
    execution: WorkflowExecution
    outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration: float
