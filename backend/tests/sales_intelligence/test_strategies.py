import pytest

from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize, Level
from app.sales_intelligence.recommendations.recommendation_engine import RecommendationEngine
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
from app.sales_intelligence.strategies.sales_strategy import SalesStrategyBase
from app.sales_intelligence.strategies.shopping_strategy import ShoppingStrategy

ALL_STRATEGIES = [
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


def _build(strategy_cls):
    rule_engine = RuleEngine([])  # isolate weight behavior from the default rule set
    return strategy_cls(ScoreCalculator(rule_engine), RecommendationEngine())


def _profile(**overrides) -> CommercialProfile:
    defaults = dict(segment=CommercialSegment.RETAIL, company_size=CompanySize.MEDIUM)
    defaults.update(overrides)
    return CommercialProfile(**defaults)


def test_sales_strategy_base_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        SalesStrategyBase(ScoreCalculator(), RecommendationEngine())


@pytest.mark.parametrize("strategy_cls", ALL_STRATEGIES)
def test_every_strategy_declares_a_unique_segment_and_weights_summing_to_one(strategy_cls):
    assert isinstance(strategy_cls.segment, CommercialSegment)
    assert abs(sum(strategy_cls._weights.values()) - 1.0) < 1e-9


def test_all_nine_segments_are_covered_by_exactly_one_strategy():
    segments = {strategy_cls.segment for strategy_cls in ALL_STRATEGIES}
    assert segments == set(CommercialSegment)


def test_calculate_produces_a_fully_populated_score():
    strategy = _build(RetailStrategy)
    profile = _profile(segment=CommercialSegment.RETAIL)

    score = strategy.calculate(profile)

    assert 0 <= score.total_score <= 100
    assert 0 <= score.conversion_probability <= 100


def test_different_strategies_weight_the_same_profile_differently():
    profile = _profile(
        segment=CommercialSegment.RETAIL,
        digital_presence=Level.HIGH,
        website_quality=Level.HIGH,
        social_presence=Level.HIGH,
    )
    retail_score = _build(RetailStrategy).calculate(profile)

    # Same profile, scored under Corporate's weighting (which discounts visibility
    # relative to Retail's) — the two total_scores must differ, proving the strategy's
    # own _weights actually drive calculate_total_score() rather than a shared default.
    corporate_profile = profile.model_copy(update={"segment": CommercialSegment.CORPORATE})
    corporate_score = _build(CorporateStrategy).calculate(corporate_profile)

    assert retail_score.total_score != corporate_score.total_score


def test_recommend_appends_one_flavor_recommendation_on_top_of_the_generic_three():
    strategy = _build(ShoppingStrategy)
    profile = _profile(segment=CommercialSegment.SHOPPING)
    score = strategy.calculate(profile)

    recommendations = strategy.recommend(profile, score)

    assert len(recommendations) == 4
    flavor = recommendations[-1]
    assert "shopping" in flavor.reason.lower() or "fluxo" in flavor.description.lower()
