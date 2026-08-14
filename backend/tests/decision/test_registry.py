import pytest

from app.decision.exceptions.decision_exceptions import NoStrategyFoundError
from app.decision.models.decision_context import DecisionContext
from app.decision.models.decision_option import DecisionOption
from app.decision.models.enums import DecisionType
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.strategies.strategy import Strategy


class _FakeStrategy(Strategy):
    def __init__(self, decision_type: DecisionType) -> None:
        self.decision_type = decision_type

    def supports(self, decision_type: DecisionType) -> bool:
        return decision_type == self.decision_type

    def decide(self, context: DecisionContext) -> list[DecisionOption]:
        return []


def test_register_returns_the_same_strategy():
    registry = StrategyRegistry()
    strategy = _FakeStrategy(DecisionType.SCORE)

    assert registry.register(strategy) is strategy


def test_get_returns_the_strategy_that_supports_the_type():
    registry = StrategyRegistry()
    score_strategy = _FakeStrategy(DecisionType.SCORE)
    priority_strategy = _FakeStrategy(DecisionType.PRIORITY)
    registry.register(score_strategy)
    registry.register(priority_strategy)

    assert registry.get(DecisionType.SCORE) is score_strategy
    assert registry.get(DecisionType.PRIORITY) is priority_strategy


def test_get_for_an_unsupported_type_raises():
    registry = StrategyRegistry()
    registry.register(_FakeStrategy(DecisionType.SCORE))

    with pytest.raises(NoStrategyFoundError):
        registry.get(DecisionType.PRIORITY)


def test_get_on_an_empty_registry_raises():
    registry = StrategyRegistry()

    with pytest.raises(NoStrategyFoundError):
        registry.get(DecisionType.SCORE)


def test_get_returns_the_first_registered_strategy_that_supports_the_type():
    registry = StrategyRegistry()
    first = _FakeStrategy(DecisionType.SCORE)
    second = _FakeStrategy(DecisionType.SCORE)
    registry.register(first)
    registry.register(second)

    assert registry.get(DecisionType.SCORE) is first


def test_list_returns_every_registered_strategy_in_order():
    registry = StrategyRegistry()
    first = _FakeStrategy(DecisionType.SCORE)
    second = _FakeStrategy(DecisionType.PRIORITY)
    registry.register(first)
    registry.register(second)

    assert registry.list() == [first, second]
