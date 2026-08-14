import pytest

from app.business_rules.builders.rule_builder import RuleBuilder
from app.business_rules.evaluators.comparison_evaluator import ComparisonEvaluator
from app.business_rules.evaluators.expression_evaluator import ExpressionEvaluator
from app.business_rules.evaluators.logical_evaluator import LogicalEvaluator
from app.business_rules.exceptions.rule_exceptions import InvalidRuleError
from app.business_rules.models.enums import ComparisonOperator, LogicalOperator
from app.business_rules.models.rule_context import RuleContext


def _recurse(rule, context):
    """A tiny stand-in for RulesEngine._evaluate_rule — dispatches to whichever
    evaluator supports the given rule, exactly like the real engine does, so
    LogicalEvaluator can be tested with real nested rules rather than a mock."""
    evaluators = [ComparisonEvaluator(), LogicalEvaluator(), ExpressionEvaluator()]
    for evaluator in evaluators:
        if evaluator.supports(rule):
            return evaluator.evaluate(rule, context, _recurse)
    raise AssertionError("no evaluator supports this rule")


@pytest.mark.parametrize(
    "operator,value,variable,expected",
    [
        (ComparisonOperator.EQUALS, "Publicidade", "Publicidade", True),
        (ComparisonOperator.EQUALS, "Publicidade", "Outra", False),
        (ComparisonOperator.NOT_EQUALS, "Fechado", "Aberto", True),
        (ComparisonOperator.GREATER_THAN, 70, 80, True),
        (ComparisonOperator.GREATER_THAN, 70, 70, False),
        (ComparisonOperator.GREATER_OR_EQUAL, 70, 70, True),
        (ComparisonOperator.LESS_THAN, 70, 60, True),
        (ComparisonOperator.LESS_OR_EQUAL, 70, 70, True),
        (ComparisonOperator.CONTAINS, "Digital", "Outdoor Digital", True),
        (ComparisonOperator.STARTS_WITH, "Outdoor", "Outdoor Digital", True),
        (ComparisonOperator.ENDS_WITH, "Digital", "Outdoor Digital", True),
    ],
)
def test_comparison_evaluator_covers_every_operator(operator, value, variable, expected):
    rule = RuleBuilder.comparison(name="check", field="field", operator=operator, value=value)
    context = RuleContext(variables={"field": variable})

    result = ComparisonEvaluator().evaluate(rule, context, _recurse)

    assert result is expected


def test_comparison_evaluator_treats_a_missing_variable_as_none_not_a_crash():
    rule = RuleBuilder.comparison(
        name="check", field="missing", operator=ComparisonOperator.GREATER_THAN, value=10
    )

    result = ComparisonEvaluator().evaluate(rule, RuleContext(), _recurse)

    assert result is False


def test_logical_and_requires_every_child_to_succeed():
    high_score = RuleBuilder.comparison(
        name="score", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )
    right_city = RuleBuilder.comparison(
        name="city", field="cidade", operator=ComparisonOperator.EQUALS, value="Goiânia"
    )
    rule = RuleBuilder.logical(
        name="qualified", operator=LogicalOperator.AND, rules=[high_score, right_city]
    )
    context = RuleContext(variables={"score": 80, "cidade": "Goiânia"})

    assert LogicalEvaluator().evaluate(rule, context, _recurse) is True

    context_failing = RuleContext(variables={"score": 50, "cidade": "Goiânia"})
    assert LogicalEvaluator().evaluate(rule, context_failing, _recurse) is False


def test_logical_or_succeeds_if_any_child_succeeds():
    a = RuleBuilder.comparison(name="a", field="x", operator=ComparisonOperator.EQUALS, value=1)
    b = RuleBuilder.comparison(name="b", field="y", operator=ComparisonOperator.EQUALS, value=1)
    rule = RuleBuilder.logical(name="either", operator=LogicalOperator.OR, rules=[a, b])

    context_true = RuleContext(variables={"x": 1, "y": 2})
    context_false = RuleContext(variables={"x": 2, "y": 2})
    assert LogicalEvaluator().evaluate(rule, context_true, _recurse) is True
    assert LogicalEvaluator().evaluate(rule, context_false, _recurse) is False


def test_logical_not_inverts_its_single_child():
    closed = RuleBuilder.comparison(
        name="closed", field="status", operator=ComparisonOperator.EQUALS, value="Fechado"
    )
    rule = RuleBuilder.logical(name="still_open", operator=LogicalOperator.NOT, rules=[closed])

    context_open = RuleContext(variables={"status": "Aberto"})
    context_closed = RuleContext(variables={"status": "Fechado"})
    assert LogicalEvaluator().evaluate(rule, context_open, _recurse) is True
    assert LogicalEvaluator().evaluate(rule, context_closed, _recurse) is False


def test_logical_not_with_more_than_one_child_raises():
    a = RuleBuilder.comparison(name="a", field="x", operator=ComparisonOperator.EQUALS, value=1)
    b = RuleBuilder.comparison(name="b", field="y", operator=ComparisonOperator.EQUALS, value=1)
    rule = RuleBuilder.logical(name="bad_not", operator=LogicalOperator.NOT, rules=[a, b])

    with pytest.raises(InvalidRuleError):
        LogicalEvaluator().evaluate(rule, RuleContext(), _recurse)


def test_logical_and_with_no_children_raises():
    rule = RuleBuilder.logical(name="empty_and", operator=LogicalOperator.AND, rules=[])

    with pytest.raises(InvalidRuleError):
        LogicalEvaluator().evaluate(rule, RuleContext(), _recurse)


def test_logical_rules_can_nest_and_or_and_not():
    high_score = RuleBuilder.comparison(
        name="score", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )
    closed = RuleBuilder.comparison(
        name="closed", field="status", operator=ComparisonOperator.EQUALS, value="Fechado"
    )
    not_closed = RuleBuilder.logical(
        name="not_closed", operator=LogicalOperator.NOT, rules=[closed]
    )
    rule = RuleBuilder.logical(
        name="qualified_and_open", operator=LogicalOperator.AND, rules=[high_score, not_closed]
    )

    context = RuleContext(variables={"score": 90, "status": "Aberto"})
    assert LogicalEvaluator().evaluate(rule, context, _recurse) is True


@pytest.mark.parametrize(
    "expression,variables,expected",
    [
        ("score >= 70", {"score": 80}, True),
        ("score >= 70", {"score": 60}, False),
        ("cidade == Goiânia", {"cidade": "Goiânia"}, True),
        ("segmento == Publicidade", {"segmento": "Retail"}, False),
        ("status != Fechado", {"status": "Aberto"}, True),
        ("valor > 5000", {"valor": 6000}, True),
        ("valor > 5000", {"valor": 5000}, False),
    ],
)
def test_expression_evaluator_covers_the_spec_examples(expression, variables, expected):
    rule = RuleBuilder.expression(name="check", expression=expression)

    result = ExpressionEvaluator().evaluate(rule, RuleContext(variables=variables), _recurse)

    assert result is expected


def test_expression_evaluator_for_an_unparsable_expression_raises():
    rule = RuleBuilder.expression(name="check", expression="not a valid expression at all")

    with pytest.raises(InvalidRuleError):
        ExpressionEvaluator().evaluate(rule, RuleContext(), _recurse)
