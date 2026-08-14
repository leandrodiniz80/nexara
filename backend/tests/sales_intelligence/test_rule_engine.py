from app.sales_intelligence.models.commercial_profile import CommercialProfile
from app.sales_intelligence.models.enums import CommercialSegment, CompanySize, Level
from app.sales_intelligence.rules.default_rules import build_default_rules
from app.sales_intelligence.rules.facts import build_facts
from app.sales_intelligence.rules.rule import Rule
from app.sales_intelligence.rules.rule_engine import RuleEngine


def _base_profile(**overrides) -> CommercialProfile:
    defaults = dict(segment=CommercialSegment.RETAIL, company_size=CompanySize.SMALL)
    defaults.update(overrides)
    return CommercialProfile(**defaults)


def test_rule_evaluate_returns_none_when_condition_does_not_match():
    rule = Rule(name="test", condition=lambda facts: facts["x"] > 10, effect={"score": 5})
    assert rule.evaluate({"x": 1}) is None


def test_rule_evaluate_returns_effect_when_condition_matches():
    rule = Rule(name="test", condition=lambda facts: facts["x"] > 10, effect={"score": 5})
    assert rule.evaluate({"x": 20}) == {"score": 5}


def test_engine_sums_numeric_effects_across_multiple_rules():
    engine = RuleEngine(
        [
            Rule(name="a", condition=lambda f: True, effect={"visibility_score": 10}),
            Rule(name="b", condition=lambda f: True, effect={"visibility_score": 5}),
        ]
    )
    result = engine.evaluate({})
    assert result.effects == {"visibility_score": 15}
    assert result.fired_rules == ["a", "b"]


def test_engine_non_numeric_effects_are_last_write_wins():
    engine = RuleEngine(
        [
            Rule(name="a", condition=lambda f: True, effect={"priority": "normal"}),
            Rule(name="b", condition=lambda f: True, effect={"priority": "high"}),
        ]
    )
    result = engine.evaluate({})
    assert result.effects == {"priority": "high"}


def test_engine_skips_rules_that_do_not_fire():
    engine = RuleEngine([Rule(name="a", condition=lambda f: False, effect={"score": 100})])
    result = engine.evaluate({})
    assert result.fired_rules == []
    assert result.effects == {}


def test_default_rule_shopping_segment_bonus():
    profile = _base_profile(segment=CommercialSegment.SHOPPING)
    engine = RuleEngine(build_default_rules())
    result = engine.evaluate(build_facts(profile))
    assert result.effects["company_score"] == 20
    assert "shopping_segment_bonus" in result.fired_rules


def test_default_rule_high_website_quality_visibility():
    profile = _base_profile(website_quality=Level.HIGH)
    engine = RuleEngine(build_default_rules())
    result = engine.evaluate(build_facts(profile))
    assert result.effects["visibility_score"] == 10


def test_default_rule_no_social_presence_hurts_relationship():
    profile = _base_profile(social_presence=Level.NONE)
    engine = RuleEngine(build_default_rules())
    result = engine.evaluate(build_facts(profile))
    assert result.effects["relationship_score"] == -5


def test_default_rule_goiania_city_sets_high_priority():
    profile = _base_profile()
    engine = RuleEngine(build_default_rules())
    result = engine.evaluate(build_facts(profile, extra_facts={"city": "Goiânia"}))
    assert result.effects["priority"] == "high"


def test_default_rule_other_city_does_not_set_priority():
    profile = _base_profile()
    engine = RuleEngine(build_default_rules())
    result = engine.evaluate(build_facts(profile, extra_facts={"city": "São Paulo"}))
    assert "priority" not in result.effects
