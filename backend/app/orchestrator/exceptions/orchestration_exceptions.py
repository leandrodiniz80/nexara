from typing import TYPE_CHECKING

from app.orchestrator.exceptions.base import OrchestrationError

if TYPE_CHECKING:
    from app.orchestrator.models.enums import OrchestrationStage


class OrchestrationStageError(OrchestrationError):
    """Raised internally when a port (Decision, Rules, Runtime, or
    Observability) raises anything at all — the Orchestrator wraps it, tagging
    which stage of the pipeline it happened at, and never lets the port's own
    exception type escape past Orchestrator.orchestrate().
    """

    def __init__(self, stage: "OrchestrationStage", cause: Exception) -> None:
        self.stage = stage
        self.cause = cause
        super().__init__(f"Orchestration failed at stage '{stage.value}': {cause}")
