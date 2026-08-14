from app.orchestrator.models.orchestration_result import OrchestrationResult


class OrchestrationRepository:
    """In-memory store of every OrchestrationResult — no database, no migration
    was requested for this module."""

    def __init__(self) -> None:
        self._results: list[OrchestrationResult] = []

    def save_result(self, result: OrchestrationResult) -> OrchestrationResult:
        self._results.append(result)
        return result

    def list_results(self) -> list[OrchestrationResult]:
        return list(self._results)
