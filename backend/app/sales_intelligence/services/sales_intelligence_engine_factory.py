from app.sales_intelligence.engine.sales_intelligence_engine import SalesIntelligenceEngine
from app.sales_intelligence.models.enums import CommercialSegment
from app.sales_intelligence.ranking.ranking_engine import RankingEngine
from app.sales_intelligence.recommendations.recommendation_engine import RecommendationEngine
from app.sales_intelligence.repositories.sales_intelligence_repository import (
    SalesIntelligenceRepository,
)
from app.sales_intelligence.rules.default_rules import build_default_rules
from app.sales_intelligence.rules.rule_engine import RuleEngine
from app.sales_intelligence.scoring.score_calculator import ScoreCalculator
from app.sales_intelligence.strategies.automotive_strategy import AutomotiveStrategy
from app.sales_intelligence.strategies.corporate_strategy import CorporateStrategy
from app.sales_intelligence.strategies.education_strategy import EducationStrategy
from app.sales_intelligence.strategies.franchise_strategy import FranchiseStrategy
from app.sales_intelligence.strategies.healthcare_strategy import HealthcareStrategy
from app.sales_intelligence.strategies.pet_strategy import PetStrategy
from app.sales_intelligence.strategies.real_estate_strategy import RealEstateStrategy
from app.sales_intelligence.strategies.retail_strategy import RetailStrategy
from app.sales_intelligence.strategies.sales_strategy import SalesStrategy, SalesStrategyBase
from app.sales_intelligence.strategies.shopping_strategy import ShoppingStrategy


def build_default_sales_intelligence_engine() -> SalesIntelligenceEngine:
    """Composition root for the Sales Intelligence module — the one place that wires
    RuleEngine + ScoreCalculator + RecommendationEngine into all nine SalesStrategy
    instances, and those into a ready SalesIntelligenceEngine. Every future caller
    (today: nothing; eventually: an integration layer feeding it from AIOrchestrator)
    should go through this rather than constructing the graph by hand.
    """
    rule_engine = RuleEngine(build_default_rules())
    score_calculator = ScoreCalculator(rule_engine)
    recommendation_engine = RecommendationEngine()

    strategy_classes: list[type[SalesStrategyBase]] = [
        RetailStrategy,
        HealthcareStrategy,
        RealEstateStrategy,
        AutomotiveStrategy,
        EducationStrategy,
        PetStrategy,
        ShoppingStrategy,
        FranchiseStrategy,
        CorporateStrategy,
    ]
    strategies: dict[CommercialSegment, SalesStrategy] = {
        strategy_cls.segment: strategy_cls(score_calculator, recommendation_engine)
        for strategy_cls in strategy_classes
    }

    return SalesIntelligenceEngine(
        strategies=strategies,
        ranking_engine=RankingEngine(),
        repository=SalesIntelligenceRepository(),
    )
