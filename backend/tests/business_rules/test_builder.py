import pytest
from pydantic import ValidationError

from app.business_rules.builders.rule_builder import RuleBuilder
from app.business_rules.models.enums import ComparisonOperator, LogicalOperator, RuleType


def test_comparison_builds_a_comparison_rule():
    rule = RuleBuilder.comparison(
        name="score_check", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )

    assert rule.rule_type == RuleType.COMPARISON
    assert rule.field == "score"
    assert rule.operator == ComparisonOperator.GREATER_OR_EQUAL
    assert rule.value == 70


def test_logical_builds_a_logical_rule_with_child_rules():
    child = RuleBuilder.comparison(
        name="city_check", field="cidade", operator=ComparisonOperator.EQUALS, value="Goiânia"
    )

    rule = RuleBuilder.logical(name="qualified", operator=LogicalOperator.AND, rules=[child])

    assert rule.rule_type == RuleType.LOGICAL
    assert rule.logical_operator == LogicalOperator.AND
    assert rule.rules == [child]


def test_expression_builds_an_expression_rule():
    rule = RuleBuilder.expression(name="valor_check", expression="valor > 5000")

    assert rule.rule_type == RuleType.EXPRESSION
    assert rule.expression == "valor > 5000"


def test_rules_are_frozen():
    rule = RuleBuilder.comparison(
        name="score_check", field="score", operator=ComparisonOperator.EQUALS, value=1
    )

    with pytest.raises(ValidationError):
        rule.name = "renamed"
