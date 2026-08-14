from pydantic import BaseModel

from app.application.tasks.context.task_context import TaskContext


class WorkflowRequest(BaseModel):
    """Input to WorkflowEngine.execute() — which registered workflow to run, and
    the TaskContext every one of its steps will be executed with."""

    workflow_name: str
    context: TaskContext
