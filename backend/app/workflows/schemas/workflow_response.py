from pydantic import BaseModel

from app.workflows.models.workflow_result import WorkflowResult


class WorkflowResponse(BaseModel):
    """Output of WorkflowEngine.execute() — a thin wrapper around WorkflowResult,
    the same "Request in, Response out" shape as every UseCase in app/application."""

    result: WorkflowResult
