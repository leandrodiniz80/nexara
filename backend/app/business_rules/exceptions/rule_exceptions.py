from typing import TYPE_CHECKING

from app.business_rules.exceptions.base import RuleError

if TYPE_CHECKING:
    from app.business_rules.models.enums import RuleType


class RuleNotFoundError(RuleError):
    """Raised when RuleRegistry.get() is asked for a rule name never registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No BusinessRule registered with name '{name}'.")


class NoEvaluatorFoundError(RuleError):
    """Raised when RulesEngine has no Evaluator registered that supports a
    rule's RuleType."""

    def __init__(self, rule_type: "RuleType") -> None:
        self.rule_type = rule_type
        super().__init__(f"No evaluator registered that supports RuleType.{rule_type.name}.")


class InvalidRuleError(RuleError):
    """Raised when a BusinessRule is malformed for its own rule_type — e.g. a
    COMPARISON missing `field`/`operator`, a LOGICAL NOT with other than one
    child rule, or an EXPRESSION string that doesn't parse."""

    def __init__(self, rule_name: str) -> None:
        self.rule_name = rule_name
        super().__init__(f"BusinessRule '{rule_name}' is invalid for its rule_type.")
