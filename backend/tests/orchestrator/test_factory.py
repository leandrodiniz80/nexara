from app.orchestrator.engine.orchestrator_factory import build_orchestrator
from app.orchestrator.models.orchestration_context import OrchestrationContext
from app.orchestrator.repositories.orchestration_repository import OrchestrationRepository


class _FakePort:
    def decide(self, context):
        return "decision"

    def evaluate(self, context):
        return "rules"

    def execute(self, context):
        return "runtime"

    def record(self, context, runtime_outcome):
        return None


def test_build_orchestrator_wires_the_given_ports():
    port = _FakePort()

    orchestrator = build_orchestrator(
        decision_port=port, rules_port=port, runtime_port=port, observability_port=port
    )

    assert orchestrator.decision_port is port
    assert orchestrator.rules_port is port
    assert orchestrator.runtime_port is port
    assert orchestrator.observability_port is port


def test_build_orchestrator_defaults_to_a_fresh_repository():
    port = _FakePort()

    orchestrator = build_orchestrator(
        decision_port=port, rules_port=port, runtime_port=port, observability_port=port
    )

    assert isinstance(orchestrator.repository, OrchestrationRepository)
    assert orchestrator.repository.list_results() == []


def test_build_orchestrator_reuses_a_given_repository():
    port = _FakePort()
    repository = OrchestrationRepository()

    orchestrator = build_orchestrator(
        decision_port=port,
        rules_port=port,
        runtime_port=port,
        observability_port=port,
        repository=repository,
    )

    assert orchestrator.repository is repository


def test_the_built_orchestrator_actually_works_end_to_end():
    port = _FakePort()
    orchestrator = build_orchestrator(
        decision_port=port, rules_port=port, runtime_port=port, observability_port=port
    )

    result = orchestrator.orchestrate(OrchestrationContext())

    assert result.success is True
