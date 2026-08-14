import pytest

from app.business_rules.builders.rule_builder import RuleBuilder
from app.business_rules.exceptions.rule_exceptions import RuleNotFoundError
from app.business_rules.models.enums import ComparisonOperator
from app.business_rules.registry.rule_registry import RuleRegistry


def _rule(name: str, value: int = 1):
    return RuleBuilder.comparison(
        name=name, field="score", operator=ComparisonOperator.EQUALS, value=value
    )


def test_register_and_get_round_trip():
    registry = RuleRegistry()
    rule = _rule("score_check")

    registry.register(rule)

    assert registry.get("score_check") is rule


def test_get_for_unknown_name_raises():
    registry = RuleRegistry()

    with pytest.raises(RuleNotFoundError):
        registry.get("does-not-exist")


def test_registering_the_same_name_again_overwrites():
    registry = RuleRegistry()
    first = _rule("score_check", value=1)
    second = _rule("score_check", value=2)
    registry.register(first)

    registry.register(second)

    assert registry.get("score_check") is second


def test_list_returns_every_registered_rule():
    registry = RuleRegistry()
    first = _rule("first")
    second = _rule("second")
    registry.register(first)
    registry.register(second)

    rules = registry.list()

    assert {r.name for r in rules} == {"first", "second"}
