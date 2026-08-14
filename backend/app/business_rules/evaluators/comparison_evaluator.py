from typing import Any, Callable

from app.business_rules.exceptions.rule_exceptions import InvalidRuleError
from app.business_rules.models.business_rule import BusinessRule
from app.business_rules.models.enums import ComparisonOperator, RuleType
from app.business_rules.models.rule_context import RuleContext

_OPERATORS: dict[ComparisonOperator, Callable[[Any, Any], bool]] = {
    ComparisonOperator.EQUALS: lambda actual, expected: actual == expected,
    ComparisonOperator.NOT_EQUALS: lambda actual, expected: actual != expected,
    ComparisonOperator.GREATER_THAN: (
        lambda actual, expected: actual is not None and actual > expected
    ),
    ComparisonOperator.GREATER_OR_EQUAL: (
        lambda actual, expected: actual is not None and actual >= expected
    ),
    ComparisonOperator.LESS_THAN: (
        lambda actual, expected: actual is not None and actual < expected
    ),
    ComparisonOperator.LESS_OR_EQUAL: (
        lambda actual, expected: actual is not None and actual <= expected
    ),
    ComparisonOperator.CONTAINS: (
        lambda actual, expected: actual is not None and expected in actual
    ),
    ComparisonOperator.STARTS_WITH: (
        lambda actual, expected: actual is not None and str(actual).startswith(str(expected))
    ),
    ComparisonOperator.ENDS_WITH: (
        lambda actual, expected: actual is not None and str(actual).endswith(str(expected))
    ),
}


def apply_comparison_operator(operator: ComparisonOperator, actual: Any, expected: Any) -> bool:
    """The one place every comparison operator is actually implemented — reused
    by both ComparisonEvaluator and ExpressionEvaluator so the two never
    duplicate operator semantics."""
    return _OPERATORS[operator](actual, expected)


class ComparisonEvaluator:
    """Evaluates a COMPARISON BusinessRule — reads `rule.field` out of
    RuleContext.variables and applies `rule.operator` against `rule.value`."""

    def supports(self, rule: BusinessRule) -> bool:
        return rule.rule_type == RuleType.COMPARISON

    def evaluate(
        self,
        rule: BusinessRule,
        context: RuleContext,
        evaluate_child: Callable[[BusinessRule, RuleContext], bool],
    ) -> bool:
        if rule.field is None or rule.operator is None:
            raise InvalidRuleError(rule.name)
        actual = context.variables.get(rule.field)
        return apply_comparison_operator(rule.operator, actual, rule.value)
