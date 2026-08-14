from app.orchestrator.engine.orchestrator import Orchestrator
from app.orchestrator.models.orchestration_context import OrchestrationContext
from app.orchestrator.repositories.orchestration_repository import OrchestrationRepository
from app.orchestrator.services.orchestration_service import OrchestrationService


class _FakePort:
    def decide(self, context):
        return "decision"

    def evaluate(self, context):
        return "rules"

    def execute(self, context):
        return "runtime"

    def record(self, context, runtime_outcome):
        return None


def _service() -> OrchestrationService:
    port = _FakePort()
    orchestrator = Orchestrator(
        decision_port=port,
        rules_port=port,
        runtime_port=port,
        observability_port=port,
        repository=OrchestrationRepository(),
    )
    return OrchestrationService(orchestrator)


def test_run_delegates_to_the_orchestrator():
    service = _service()

    result = service.run(OrchestrationContext(request_id="req-1"))

    assert result.success is True
    assert result.decision == "decision"
    assert result.rules_outcome == "rules"
    assert result.runtime_outcome == "runtime"


def test_history_returns_every_past_result():
    service = _service()

    first = service.run(OrchestrationContext())
    second = service.run(OrchestrationContext())

    assert service.history() == [first, second]


def test_history_is_empty_before_any_run():
    service = _service()

    assert service.history() == []
