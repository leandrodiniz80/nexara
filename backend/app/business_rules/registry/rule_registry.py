from app.business_rules.exceptions.rule_exceptions import RuleNotFoundError
from app.business_rules.models.business_rule import BusinessRule


class RuleRegistry:
    """Holds every registered BusinessRule, keyed by name — one per name, the
    most recently registered one wins."""

    def __init__(self) -> None:
        self._rules: dict[str, BusinessRule] = {}

    def register(self, rule: BusinessRule) -> BusinessRule:
        self._rules[rule.name] = rule
        return rule

    def get(self, name: str) -> BusinessRule:
        rule = self._rules.get(name)
        if rule is None:
            raise RuleNotFoundError(name)
        return rule

    def list(self) -> list[BusinessRule]:
        return list(self._rules.values())
