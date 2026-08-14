from pydantic import BaseModel

from app.automation.models.automation_execution import AutomationExecution
from app.workflows.models.workflow_result import WorkflowResult


class AutomationResponse(BaseModel):
    """Output of every AutomationEngine.execute*() call — the AutomationExecution
    record plus the underlying WorkflowResult it produced."""

    execution: AutomationExecution
    workflow_result: WorkflowResult
