from app.orchestrator.engine.orchestrator import Orchestrator
from app.orchestrator.models.enums import OrchestrationStage
from app.orchestrator.models.orchestration_context import OrchestrationContext
from app.orchestrator.repositories.orchestration_repository import OrchestrationRepository


class _FakeDecisionPort:
    def __init__(
        self, *, raises: Exception | None = None, value: object = "chosen_workflow"
    ) -> None:
        self.raises = raises
        self.value = value
        self.calls: list[OrchestrationContext] = []

    def decide(self, context: OrchestrationContext) -> object:
        self.calls.append(context)
        if self.raises is not None:
            raise self.raises
        return self.value


class _FakeRulesPort:
    def __init__(self, *, raises: Exception | None = None, value: object = "rules_passed") -> None:
        self.raises = raises
        self.value = value
        self.calls: list[OrchestrationContext] = []

    def evaluate(self, context: OrchestrationContext) -> object:
        self.calls.append(context)
        if self.raises is not None:
            raise self.raises
        return self.value


class _FakeRuntimePort:
    def __init__(self, *, raises: Exception | None = None, value: object = "executed") -> None:
        self.raises = raises
        self.value = value
        self.calls: list[OrchestrationContext] = []

    def execute(self, context: OrchestrationContext) -> object:
        self.calls.append(context)
        if self.raises is not None:
            raise self.raises
        return self.value


class _FakeObservabilityPort:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.raises = raises
        self.recorded: list[tuple[OrchestrationContext, object]] = []

    def record(self, context: OrchestrationContext, runtime_outcome: object) -> None:
        if self.raises is not None:
            raise self.raises
        self.recorded.append((context, runtime_outcome))


def _orchestrator(**overrides) -> tuple[Orchestrator, dict]:
    ports = {
        "decision_port": _FakeDecisionPort(),
        "rules_port": _FakeRulesPort(),
        "runtime_port": _FakeRuntimePort(),
        "observability_port": _FakeObservabilityPort(),
    }
    ports.update(overrides)
    orchestrator = Orchestrator(repository=OrchestrationRepository(), **ports)
    return orchestrator, ports


def test_orchestrate_calls_every_port_in_order_and_succeeds():
    orchestrator, ports = _orchestrator()
    context = OrchestrationContext(request_id="req-1")

    result = orchestrator.orchestrate(context)

    assert result.success is True
    assert result.stage_reached == OrchestrationStage.COMPLETED
    assert result.decision == "chosen_workflow"
    assert result.rules_outcome == "rules_passed"
    assert result.runtime_outcome == "executed"
    assert result.reason is None
    assert ports["decision_port"].calls == [context]
    assert ports["rules_port"].calls == [context]
    assert ports["runtime_port"].calls == [context]
    assert ports["observability_port"].recorded == [(context, "executed")]


def test_orchestrate_persists_the_result_in_the_repository():
    orchestrator, _ = _orchestrator()

    result = orchestrator.orchestrate(OrchestrationContext())

    assert orchestrator.repository.list_results() == [result]


def test_orchestrate_stops_at_decision_stage_when_decision_port_raises():
    orchestrator, _ = _orchestrator(decision_port=_FakeDecisionPort(raises=ValueError("boom")))

    result = orchestrator.orchestrate(OrchestrationContext())

    assert result.success is False
    assert result.stage_reached == OrchestrationStage.DECISION
    assert result.decision is None
    assert result.rules_outcome is None
    assert result.runtime_outcome is None
    assert "boom" in result.reason


def test_orchestrate_stops_at_rules_stage_when_rules_port_raises():
    orchestrator, _ = _orchestrator(rules_port=_FakeRulesPort(raises=ValueError("bad rule")))

    result = orchestrator.orchestrate(OrchestrationContext())

    assert result.success is False
    assert result.stage_reached == OrchestrationStage.RULES
    assert result.decision == "chosen_workflow"
    assert result.rules_outcome is None
    assert result.runtime_outcome is None


def test_orchestrate_stops_at_runtime_stage_when_runtime_port_raises():
    orchestrator, _ = _orchestrator(runtime_port=_FakeRuntimePort(raises=RuntimeError("failed")))

    result = orchestrator.orchestrate(OrchestrationContext())

    assert result.success is False
    assert result.stage_reached == OrchestrationStage.RUNTIME
    assert result.decision == "chosen_workflow"
    assert result.rules_outcome == "rules_passed"
    assert result.runtime_outcome is None


def test_orchestrate_stops_at_observability_stage_when_observability_port_raises():
    orchestrator, _ = _orchestrator(
        observability_port=_FakeObservabilityPort(raises=ConnectionError("unreachable"))
    )

    result = orchestrator.orchestrate(OrchestrationContext())

    assert result.success is False
    assert result.stage_reached == OrchestrationStage.OBSERVABILITY
    assert result.decision == "chosen_workflow"
    assert result.rules_outcome == "rules_passed"
    assert result.runtime_outcome == "executed"


def test_orchestrator_never_imports_any_real_module():
    import app.orchestrator.engine.orchestrator as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    for forbidden in (
        "app.workflows",
        "app.automation",
        "app.runtime",
        "app.crm",
        "app.platform",
        "app.business_rules",
        "app.decision",
        "app.mission",
        "app.research",
        "app.ai",
        "app.application",
        "app.api",
        "app.observability",
    ):
        assert forbidden not in source
