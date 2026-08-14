from typing import Callable

from app.business_rules.exceptions.rule_exceptions import InvalidRuleError
from app.business_rules.models.business_rule import BusinessRule
from app.business_rules.models.enums import LogicalOperator, RuleType
from app.business_rules.models.rule_context import RuleContext


class LogicalEvaluator:
    """Evaluates a LOGICAL BusinessRule (AND/OR/NOT) by recursing into each child
    rule through the `evaluate_child` callback RulesEngine passes at call time —
    never evaluating a child's Comparison/Expression logic itself, and never
    importing RulesEngine (which would create a construction-order cycle: the
    engine needs its evaluators built before it exists, and an evaluator needing
    a live reference to the engine would need the engine to exist first).
    """

    def supports(self, rule: BusinessRule) -> bool:
        return rule.rule_type == RuleType.LOGICAL

    def evaluate(
        self,
        rule: BusinessRule,
        context: RuleContext,
        evaluate_child: Callable[[BusinessRule, RuleContext], bool],
    ) -> bool:
        if rule.logical_operator is None:
            raise InvalidRuleError(rule.name)

        if rule.logical_operator == LogicalOperator.NOT:
            if len(rule.rules) != 1:
                raise InvalidRuleError(rule.name)
            return not evaluate_child(rule.rules[0], context)

        if not rule.rules:
            raise InvalidRuleError(rule.name)

        if rule.logical_operator == LogicalOperator.AND:
            return all(evaluate_child(child, context) for child in rule.rules)

        return any(evaluate_child(child, context) for child in rule.rules)
