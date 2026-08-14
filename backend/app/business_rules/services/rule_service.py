from app.business_rules.engine.rules_engine import RulesEngine
from app.business_rules.models.business_rule import BusinessRule
from app.business_rules.models.rule_context import RuleContext
from app.business_rules.models.rule_result import RuleResult


class RuleService:
    """A thin facade over RulesEngine for name-based call patterns — register
    several rules at once, evaluate a rule already registered by name (resolving
    it through the engine's own registry first). It implements no rule logic of
    its own; it only forwards to RulesEngine.
    """

    def __init__(self, engine: RulesEngine) -> None:
        self.engine = engine

    def register_many(self, rules: list[BusinessRule]) -> list[BusinessRule]:
        return [self.engine.register(rule) for rule in rules]

    def evaluate_by_name(self, rule_name: str, context: RuleContext) -> RuleResult:
        rule = self.engine.registry.get(rule_name)
        return self.engine.evaluate(rule, context)

    def evaluate_all_by_name(
        self, rule_names: list[str], context: RuleContext
    ) -> list[RuleResult]:
        rules = [self.engine.registry.get(name) for name in rule_names]
        return self.engine.evaluate_all(rules, context)
