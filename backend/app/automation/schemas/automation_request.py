from pydantic import BaseModel

from app.workflows.schemas.workflow_request import WorkflowRequest


class AutomationRequest(BaseModel):
    """Input to AutomationEngine.execute() — which registered Automation to run,
    and the WorkflowRequest (workflow_name + TaskContext) to hand to WorkflowEngine.

    Embedding the whole WorkflowRequest here — rather than a bare TaskContext field
    — is deliberate: AutomationEngine is only allowed to know WorkflowEngine,
    WorkflowRequest and WorkflowResult, never TaskContext directly. The engine
    itself ignores `workflow_request.workflow_name` and uses the registered
    Automation's own `workflow_name` instead, so the two can never disagree.
    """

    automation_name: str
    workflow_request: WorkflowRequest
