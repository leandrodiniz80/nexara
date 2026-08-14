from app.decision.engine.decision_engine import DecisionEngine
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.repositories.decision_repository import DecisionRepository
from app.decision.strategies.priority_strategy import PriorityStrategy
from app.decision.strategies.recommendation_strategy import RecommendationStrategy
from app.decision.strategies.routing_strategy import RoutingStrategy
from app.decision.strategies.score_strategy import ScoreStrategy


def build_default_decision_engine(
    *,
    registry: StrategyRegistry | None = None,
    repository: DecisionRepository | None = None,
) -> DecisionEngine:
    """Composition root for this module — registers the four generic Strategies
    (Priority, Score, Routing, Recommendation) covering all eight DecisionTypes.
    No specific business decision is ever pre-registered: each Strategy only
    reads a generically-named list out of DecisionContext.variables.
    """
    engine = DecisionEngine(
        registry=registry or StrategyRegistry(), repository=repository or DecisionRepository()
    )
    for strategy in (
        PriorityStrategy(),
        ScoreStrategy(),
        RoutingStrategy(),
        RecommendationStrategy(),
    ):
        engine.register_strategy(strategy)
    return engine
