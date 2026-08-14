from app.decision.engine.decision_engine import DecisionEngine
from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_result import DecisionResult
from app.decision.models.enums import DecisionType
from app.decision.strategies.strategy import Strategy


class DecisionService:
    """A thin facade over DecisionEngine — registers several Strategies at once
    and forwards decide()/decide_all() unchanged. It implements no decision
    logic of its own.
    """

    def __init__(self, engine: DecisionEngine) -> None:
        self.engine = engine

    def register_many(self, strategies: list[Strategy]) -> list[Strategy]:
        return [self.engine.register_strategy(strategy) for strategy in strategies]

    def decide(
        self, decision_type: DecisionType, context: DecisionContext, *, priority: int = 0
    ) -> DecisionResult:
        return self.engine.decide(decision_type, context, priority=priority)

    def decide_all(
        self, decision_types: list[DecisionType], context: DecisionContext, *, priority: int = 0
    ) -> list[DecisionResult]:
        return self.engine.decide_all(decision_types, context, priority=priority)
