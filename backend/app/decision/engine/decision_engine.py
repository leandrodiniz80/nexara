import time

from app.decision.exceptions.base import DecisionError
from app.decision.exceptions.decision_exceptions import NoCandidateOptionsError
from app.decision.models.decision import Decision
from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.decision_result import DecisionResult
from app.decision.models.enums import DecisionType
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.repositories.decision_repository import DecisionRepository
from app.decision.strategies.strategy import Strategy


class DecisionEngine:
    """A generic decision-making engine — it receives a DecisionContext and
    returns a DecisionResult. It executes nothing: it never calls Workflow,
    Runtime, Automation, CRM, or AI, and it doesn't even know Business Rules
    exists. It only asks its registered Strategies for candidate
    DecisionOptions and picks the best-scoring one.
    """

    def __init__(self, registry: StrategyRegistry, repository: DecisionRepository) -> None:
        self.registry = registry
        self.repository = repository

    def register_strategy(self, strategy: Strategy) -> Strategy:
        return self.registry.register(strategy)

    def list_strategies(self) -> list[Strategy]:
        return self.registry.list()

    def decide(
        self, decision_type: DecisionType, context: DecisionContext, *, priority: int = 0
    ) -> DecisionResult:
        start = time.perf_counter()
        candidates: list[DecisionOption] = []
        selected: DecisionOption | None = None
        reason: str | None = None

        try:
            strategy = self.registry.get(decision_type)
            candidates = strategy.decide(context)
            if not candidates:
                raise NoCandidateOptionsError(decision_type)
            selected = max(candidates, key=lambda option: option.score)
            success = True
        except DecisionError as exc:
            success = False
            reason = str(exc)

        execution_time = time.perf_counter() - start

        if selected is not None:
            self.repository.save_decision(
                Decision(
                    name=selected.name,
                    type=decision_type,
                    priority=priority,
                    score=selected.score,
                    payload=selected.payload,
                )
            )

        return DecisionResult(
            selected_option=selected,
            candidate_options=candidates,
            execution_time=execution_time,
            success=success,
            reason=reason,
        )

    def decide_all(
        self, decision_types: list[DecisionType], context: DecisionContext, *, priority: int = 0
    ) -> list[DecisionResult]:
        return [self.decide(dt, context, priority=priority) for dt in decision_types]
