from app.orchestrator.engine.orchestrator import Orchestrator
from app.orchestrator.models.orchestration_context import OrchestrationContext
from app.orchestrator.models.orchestration_result import OrchestrationResult


class OrchestrationService:
    """A thin facade over Orchestrator — the future single entrypoint CLI/API/
    Workers/Scheduler will call to run one orchestration and inspect past ones.
    It implements no coordination logic of its own; it only forwards to
    Orchestrator.
    """

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    def run(self, context: OrchestrationContext) -> OrchestrationResult:
        return self.orchestrator.orchestrate(context)

    def history(self) -> list[OrchestrationResult]:
        return self.orchestrator.repository.list_results()
