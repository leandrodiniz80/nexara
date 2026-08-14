import time
from typing import Any, Protocol

from app.orchestrator.exceptions.orchestration_exceptions import OrchestrationStageError
from app.orchestrator.models.enums import OrchestrationStage
from app.orchestrator.models.orchestration_context import OrchestrationContext
from app.orchestrator.models.orchestration_result import OrchestrationResult
from app.orchestrator.repositories.orchestration_repository import OrchestrationRepository


class DecisionPort(Protocol):
    """Structural stand-in for whatever will consult Decision in a future
    sprint. This sprint defines the shape only — no real Decision Engine is
    imported or called; tests inject fakes satisfying this Protocol.
    """

    def decide(self, context: OrchestrationContext) -> Any: ...


class RulesPort(Protocol):
    """Structural stand-in for whatever will consult Business Rules in a
    future sprint. No real Rules Engine is imported or called here."""

    def evaluate(self, context: OrchestrationContext) -> Any: ...


class RuntimePort(Protocol):
    """Structural stand-in for whatever will execute via Runtime in a future
    sprint. No real Runtime Engine is imported or called here."""

    def execute(self, context: OrchestrationContext) -> Any: ...


class ObservabilityPort(Protocol):
    """Structural stand-in for whatever will record Observability in a future
    sprint. No real Observability module is imported or called here."""

    def record(self, context: OrchestrationContext, runtime_outcome: Any) -> None: ...


class Orchestrator:
    """The platform's single point of coordination. It implements no business
    rule and executes no logic of its own — it only calls, in order, whichever
    Decision/Rules/Runtime/Observability ports were injected into it, and
    reports what happened. This sprint integrates no real module: the four
    ports above are Protocols only, satisfied here by fakes; a future sprint
    will supply adapters wrapping the real DecisionEngine/RulesEngine/
    RuntimeEngine/Observability.

    Every port call is wrapped in a broad `except Exception` on purpose: this
    module is forbidden from importing any real module's exception types (that
    would itself be an integration this sprint doesn't do), so it cannot catch
    anything more specific than the base `Exception` a port might raise.
    """

    def __init__(
        self,
        decision_port: DecisionPort,
        rules_port: RulesPort,
        runtime_port: RuntimePort,
        observability_port: ObservabilityPort,
        repository: OrchestrationRepository,
    ) -> None:
        self.decision_port = decision_port
        self.rules_port = rules_port
        self.runtime_port = runtime_port
        self.observability_port = observability_port
        self.repository = repository

    def orchestrate(self, context: OrchestrationContext) -> OrchestrationResult:
        start = time.perf_counter()
        decision: Any = None
        rules_outcome: Any = None
        runtime_outcome: Any = None
        reason: str | None = None

        try:
            decision = self._consult_decision(context)
            rules_outcome = self._consult_rules(context)
            runtime_outcome = self._execute_runtime(context)
            self._register_observability(context, runtime_outcome)
            stage_reached = OrchestrationStage.COMPLETED
            success = True
        except OrchestrationStageError as exc:
            stage_reached = exc.stage
            success = False
            reason = str(exc)

        execution_time = time.perf_counter() - start

        result = OrchestrationResult(
            success=success,
            stage_reached=stage_reached,
            decision=decision,
            rules_outcome=rules_outcome,
            runtime_outcome=runtime_outcome,
            execution_time=execution_time,
            reason=reason,
        )
        self.repository.save_result(result)
        return result

    def _consult_decision(self, context: OrchestrationContext) -> Any:
        try:
            return self.decision_port.decide(context)
        except Exception as exc:
            raise OrchestrationStageError(OrchestrationStage.DECISION, exc) from exc

    def _consult_rules(self, context: OrchestrationContext) -> Any:
        try:
            return self.rules_port.evaluate(context)
        except Exception as exc:
            raise OrchestrationStageError(OrchestrationStage.RULES, exc) from exc

    def _execute_runtime(self, context: OrchestrationContext) -> Any:
        try:
            return self.runtime_port.execute(context)
        except Exception as exc:
            raise OrchestrationStageError(OrchestrationStage.RUNTIME, exc) from exc

    def _register_observability(self, context: OrchestrationContext, runtime_outcome: Any) -> None:
        try:
            self.observability_port.record(context, runtime_outcome)
        except Exception as exc:
            raise OrchestrationStageError(OrchestrationStage.OBSERVABILITY, exc) from exc
