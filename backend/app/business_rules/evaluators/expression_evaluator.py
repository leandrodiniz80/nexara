import re
from typing import Any, Callable

from app.business_rules.evaluators.comparison_evaluator import apply_comparison_operator
from app.business_rules.exceptions.rule_exceptions import InvalidRuleError
from app.business_rules.models.business_rule import BusinessRule
from app.business_rules.models.enums import ComparisonOperator, RuleType
from app.business_rules.models.rule_context import RuleContext

_SYMBOL_TO_OPERATOR: dict[str, ComparisonOperator] = {
    "==": ComparisonOperator.EQUALS,
    "!=": ComparisonOperator.NOT_EQUALS,
    ">=": ComparisonOperator.GREATER_OR_EQUAL,
    "<=": ComparisonOperator.LESS_OR_EQUAL,
    ">": ComparisonOperator.GREATER_THAN,
    "<": ComparisonOperator.LESS_THAN,
}
_EXPRESSION_PATTERN = re.compile(r"^\s*(\S+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


class ExpressionEvaluator:
    """Evaluates an EXPRESSION BusinessRule — a raw string like "score >= 70" or
    "cidade == Goiânia" — by parsing it into a field/operator/value triple and
    reusing apply_comparison_operator(), the same function ComparisonEvaluator
    itself calls, rather than duplicating the operator semantics.
    """

    def supports(self, rule: BusinessRule) -> bool:
        return rule.rule_type == RuleType.EXPRESSION

    def evaluate(
        self,
        rule: BusinessRule,
        context: RuleContext,
        evaluate_child: Callable[[BusinessRule, RuleContext], bool],
    ) -> bool:
        if rule.expression is None:
            raise InvalidRuleError(rule.name)
        field, operator, expected = self._parse(rule)
        actual = context.variables.get(field)
        return apply_comparison_operator(operator, actual, expected)

    def _parse(self, rule: BusinessRule) -> tuple[str, ComparisonOperator, Any]:
        match = _EXPRESSION_PATTERN.match(rule.expression)
        if match is None:
            raise InvalidRuleError(rule.name)
        field, symbol, raw_value = match.groups()
        return field, _SYMBOL_TO_OPERATOR[symbol], self._coerce(raw_value)

    @staticmethod
    def _coerce(raw_value: str) -> Any:
        try:
            return int(raw_value)
        except ValueError:
            pass
        try:
            return float(raw_value)
        except ValueError:
            pass
        return raw_value
