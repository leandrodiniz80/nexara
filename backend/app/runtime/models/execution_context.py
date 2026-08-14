import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.automation.schemas.automation_request import AutomationRequest
from app.workflows.schemas.workflow_request import WorkflowRequest


class ExecutionContext(BaseModel):
    """Everything one RuntimeEngine.execute() call needs — carries a request for
    every ExecutionType an Executor might exist for, all optional: a caller fills
    in only the one matching whatever `execution_type` it's asking for
    (`workflow_request` for WORKFLOW, `automation_request` for AUTOMATION); the
    matching Executor is responsible for checking its own field is set (see
    MissingExecutionRequestError).

    `job_request` has no typed shape yet — JobExecutor is infrastructure-only this
    sprint (raises NotImplementedError), so there is no real request schema to
    reference. `request_id`/`user_id`/`mission_id` are the same "bare cross-module
    reference, never the full entity" convention every other Context in this
    platform (TaskContext, TraceContext) already uses.
    """

    request_id: str | None = None
    user_id: uuid.UUID | None = None
    mission_id: uuid.UUID | None = None
    workflow_request: WorkflowRequest | None = None
    automation_request: AutomationRequest | None = None
    job_request: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
