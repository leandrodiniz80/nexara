from app.orchestrator.engine.orchestrator import (
    DecisionPort,
    ObservabilityPort,
    Orchestrator,
    RulesPort,
    RuntimePort,
)
from app.orchestrator.repositories.orchestration_repository import OrchestrationRepository


def build_orchestrator(
    *,
    decision_port: DecisionPort,
    rules_port: RulesPort,
    runtime_port: RuntimePort,
    observability_port: ObservabilityPort,
    repository: OrchestrationRepository | None = None,
) -> Orchestrator:
    """Composition root for this module. Unlike every other module's factory in
    this codebase, this one has no real default to fall back to: Decision/
    Rules/Runtime/Observability integration doesn't exist yet — that's a future
    sprint's job — so all four ports must be supplied by the caller. Only the
    repository defaults to a fresh in-memory store.
    """
    return Orchestrator(
        decision_port=decision_port,
        rules_port=rules_port,
        runtime_port=runtime_port,
        observability_port=observability_port,
        repository=repository or OrchestrationRepository(),
    )
