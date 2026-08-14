from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import (
    CommercialSegment,
    CommunicationStyle,
    CompanySize,
    DecisionSpeed,
    Level,
    MarketingMaturity,
    Priority,
    RevenueRange,
)
from app.sales_intelligence.rules.rule import Rule
from app.sales_intelligence.rules.rule_engine import RuleEngine
from app.sales_intelligence.scoring.score_calculator import ScoreCalculator


def _profile(**overrides) -> CommercialProfile:
    defaults = dict(segment=CommercialSegment.RETAIL, company_size=CompanySize.MICRO)
    defaults.update(overrides)
    return CommercialProfile(**defaults)


def test_calculate_company_score_baseline_with_no_rules_firing():
    calculator = ScoreCalculator(RuleEngine([]))
    profile = _profile(company_size=CompanySize.MICRO, estimated_revenue=RevenueRange.UNKNOWN)
    assert calculator.calculate_company_score(profile) == 10


def test_calculate_company_score_applies_default_shopping_rule():
    calculator = ScoreCalculator()  # default rule set
    profile = _profile(segment=CommercialSegment.SHOPPING, company_size=CompanySize.MICRO)
    # baseline 10 + rule bonus 20 = 30
    assert calculator.calculate_company_score(profile) == 30


def test_calculate_visibility_sums_the_three_level_components():
    calculator = ScoreCalculator(RuleEngine([]))
    profile = _profile(
        digital_presence=Level.HIGH, website_quality=Level.HIGH, social_presence=Level.HIGH
    )
    assert calculator.calculate_visibility(profile) == 90


def test_calculate_relationship_penalized_by_missing_social_presence():
    calculator = ScoreCalculator()  # default rules include the "no social presence" penalty
    profile = _profile(communication_style=CommunicationStyle.FORMAL, social_presence=Level.NONE)
    # baseline: formal(10) + social_presence NONE(0) = 10, then -5 from the default rule
    assert calculator.calculate_relationship(profile) == 5


def test_calculate_score_never_goes_below_zero():
    huge_penalty = Rule(
        name="huge_penalty", condition=lambda f: True, effect={"relationship_score": -1000}
    )
    calculator = ScoreCalculator(RuleEngine([huge_penalty]))
    profile = _profile()
    assert calculator.calculate_relationship(profile) == 0


def test_calculate_score_never_exceeds_100():
    huge_bonus = Rule(
        name="huge_bonus", condition=lambda f: True, effect={"visibility_score": 1000}
    )
    calculator = ScoreCalculator(RuleEngine([huge_bonus]))
    profile = _profile(
        digital_presence=Level.HIGH, website_quality=Level.HIGH, social_presence=Level.HIGH
    )
    assert calculator.calculate_visibility(profile) == 100


def test_calculate_priority_uses_rule_override_when_present():
    always_urgent = Rule(
        name="always_urgent", condition=lambda f: True, effect={"priority": "urgent"}
    )
    calculator = ScoreCalculator(RuleEngine([always_urgent]))
    profile = _profile()
    assert calculator.calculate_priority(profile) == Priority.URGENT


def test_calculate_priority_falls_back_to_urgency_when_no_rule_fires():
    calculator = ScoreCalculator(RuleEngine([]))
    fast_mover = _profile(decision_speed=DecisionSpeed.FAST, competitive_level=Level.HIGH)
    slow_mover = _profile(decision_speed=DecisionSpeed.SLOW, competitive_level=Level.NONE)

    assert calculator.calculate_priority(fast_mover) in (Priority.HIGH, Priority.URGENT)
    assert calculator.calculate_priority(slow_mover) == Priority.LOW


def test_calculate_priority_reads_city_from_extra_facts():
    calculator = ScoreCalculator()  # default rules include the Goiânia -> HIGH rule
    profile = _profile()
    assert calculator.calculate_priority(profile, extra_facts={"city": "Goiânia"}) == Priority.HIGH


def test_calculate_total_score_uses_default_weights():
    calculator = ScoreCalculator(RuleEngine([]))
    total = calculator.calculate_total_score(
        company_score=100,
        potential_score=0,
        urgency_score=0,
        visibility_score=0,
        relationship_score=0,
    )
    assert total == 30  # 100 * 0.30 default weight for company_score


def test_calculate_total_score_honors_custom_weights():
    calculator = ScoreCalculator(RuleEngine([]))
    total = calculator.calculate_total_score(
        company_score=0,
        potential_score=0,
        urgency_score=0,
        visibility_score=100,
        relationship_score=0,
        weights={
            "company_score": 0.1,
            "potential_score": 0.1,
            "urgency_score": 0.1,
            "visibility_score": 0.6,
            "relationship_score": 0.1,
        },
    )
    assert total == 60


def test_calculate_conversion_probability_rewards_marketing_maturity():
    calculator = ScoreCalculator(RuleEngine([]))
    mature = _profile(marketing_maturity=MarketingMaturity.ADVANCED)
    immature = _profile(marketing_maturity=MarketingMaturity.NONE)
    assert calculator.calculate_conversion_probability(
        mature
    ) > calculator.calculate_conversion_probability(immature)
