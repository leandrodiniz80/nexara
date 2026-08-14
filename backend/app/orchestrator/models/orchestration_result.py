from typing import Any

from pydantic import BaseModel

from app.orchestrator.models.enums import OrchestrationStage


class OrchestrationResult(BaseModel):
    """What every Orchestrator.orchestrate() call returns — the same "always a
    result, never a raised exception past this boundary" shape as every other
    *Result type in this codebase. `decision`/`rules_outcome`/`runtime_outcome`
    are intentionally untyped: this sprint's ports return whatever a fake
    implementation hands back, and the Orchestrator has no business inspecting
    their shape — it only threads them through to this report.
    """

    success: bool
    stage_reached: OrchestrationStage
    decision: Any | None = None
    rules_outcome: Any | None = None
    runtime_outcome: Any | None = None
    execution_time: float
    reason: str | None = None
