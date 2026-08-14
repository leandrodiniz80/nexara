from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.application.tasks.base.application_task import TaskType


class WorkflowStep(BaseModel):
    """One step in a Workflow's sequence — which ApplicationTask to run and how to
    treat its failure. Frozen: a Workflow's definition doesn't change once built
    (WorkflowBuilder produces a new Workflow rather than mutating an existing one's
    steps) — the same "definition is immutable, only runtime state (WorkflowExecution)
    mutates" split as AssetTemplate/OutreachAsset.

    `required` is stored but not behaviorally enforced by this sprint's
    WorkflowEngine (only `continue_on_error` drives the pause/continue decision,
    per the spec) — it's descriptive metadata a future caller/UI can read.
    `timeout`, when set, IS enforced: WorkflowEngine.execute_step() wraps the task
    call so a step that hangs still fails like any other step, without touching
    TaskExecutor itself.
    """

    model_config = ConfigDict(frozen=True)

    order: int
    task_type: TaskType
    name: str
    required: bool = True
    continue_on_error: bool = False
    timeout: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
