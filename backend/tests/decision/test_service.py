from app.decision.builders.decision_builder import DecisionBuilder
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.models.enums import DecisionType
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.repositories.decision_repository import DecisionRepository
from app.decision.services.decision_service import DecisionService
from app.decision.strategies.priority_strategy import PriorityStrategy
from app.decision.strategies.score_strategy import ScoreStrategy


def _service() -> DecisionService:
    engine = DecisionEngine(registry=StrategyRegistry(), repository=DecisionRepository())
    return DecisionService(engine)


def test_register_many_registers_every_strategy():
    service = _service()

    registered = service.register_many([ScoreStrategy(), PriorityStrategy()])

    assert registered == service.engine.list_strategies()
    assert len(service.engine.list_strategies()) == 2


def test_decide_forwards_to_the_engine():
    service = _service()
    service.register_many([ScoreStrategy()])
    context = DecisionBuilder.context(variables={"options": [{"name": "A", "score": 1}]})

    result = service.decide(DecisionType.SCORE, context)

    assert result.success is True
    assert result.selected_option.name == "A"


def test_decide_all_forwards_to_the_engine():
    service = _service()
    service.register_many([ScoreStrategy(), PriorityStrategy()])
    context = DecisionBuilder.context(
        variables={
            "options": [{"name": "A", "score": 1}],
            "candidates": [{"name": "B", "priority": 1}],
        }
    )

    results = service.decide_all([DecisionType.SCORE, DecisionType.PRIORITY], context)

    assert [r.selected_option.name for r in results] == ["A", "B"]
