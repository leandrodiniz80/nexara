from app.decision.exceptions.decision_exceptions import NoStrategyFoundError
from app.decision.models.enums import DecisionType
from app.decision.strategies.strategy import Strategy


class StrategyRegistry:
    """Holds every registered Strategy and finds the one that supports a given
    DecisionType — a plain list, checked via each Strategy's own `supports()`,
    the same Strategy-pattern dispatch as ExecutorRegistry in app.runtime.
    """

    def __init__(self) -> None:
        self._strategies: list[Strategy] = []

    def register(self, strategy: Strategy) -> Strategy:
        self._strategies.append(strategy)
        return strategy

    def get(self, decision_type: DecisionType) -> Strategy:
        for strategy in self._strategies:
            if strategy.supports(decision_type):
                return strategy
        raise NoStrategyFoundError(decision_type)

    def list(self) -> list[Strategy]:
        return list(self._strategies)
