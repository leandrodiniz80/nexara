from typing import Any

from app.business_rules.models.business_rule import BusinessRule
from app.business_rules.models.enums import ComparisonOperator, LogicalOperator, RuleType


class RuleBuilder:
    """Constructs BusinessRules — the only place this construction logic lives,
    the same role WorkflowBuilder/PipelineBuilder play for their own modules."""

    @staticmethod
    def comparison(
        *,
        name: str,
        field: str,
        operator: ComparisonOperator,
        value: Any,
        description: str | None = None,
    ) -> BusinessRule:
        return BusinessRule(
            name=name,
            rule_type=RuleType.COMPARISON,
            field=field,
            operator=operator,
            value=value,
            description=description,
        )

    @staticmethod
    def logical(
        *,
        name: str,
        operator: LogicalOperator,
        rules: list[BusinessRule],
        description: str | None = None,
    ) -> BusinessRule:
        return BusinessRule(
            name=name,
            rule_type=RuleType.LOGICAL,
            logical_operator=operator,
            rules=rules,
            description=description,
        )

    @staticmethod
    def expression(*, name: str, expression: str, description: str | None = None) -> BusinessRule:
        return BusinessRule(
            name=name, rule_type=RuleType.EXPRESSION, expression=expression, description=description
        )
