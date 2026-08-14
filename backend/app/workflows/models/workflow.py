import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.workflows.models.workflow_step import WorkflowStep


class Workflow(BaseModel):
    """A named, versioned sequence of WorkflowSteps — the definition, not a run of
    it (that's WorkflowExecution). Frozen: WorkflowBuilder always produces a fresh
    Workflow rather than mutating one in place, the same reasoning as AssetTemplate
    — a definition that changed in place out from under an in-flight execution
    would be a real bug, not a feature.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    version: int = 1
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
