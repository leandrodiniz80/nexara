from typing import Any

from pydantic import BaseModel, Field

from app.runtime.models.execution import Execution


class ExecutionResult(BaseModel):
    """What every RuntimeEngine.execute*() call returns — the same "always a
    result, never a raised exception past this boundary" shape as every other
    *Result type in this codebase (TaskResult, WorkflowResult, ApplicationServiceResult).
    `payload` is intentionally untyped: a WorkflowExecutor puts WorkflowResult.outputs
    there, an AutomationExecutor puts the underlying WorkflowResult.outputs there
    too — each Executor decides what's meaningful for its own ExecutionType.
    """

    success: bool
    execution: Execution
    payload: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
