from typing import Any

from app.business_rules.engine.rules_engine import RulesEngine
from app.business_rules.models.rule_context import RuleContext


class RulesAdapter:
    """Optional pre-check VerticalSlice consults before invoking Runtime —
    evaluates every BusinessRule currently registered with the real
    RulesEngine against the execution's variables. If none are registered,
    everything is considered eligible (there is nothing to fail); if any
    registered rule fails, the vertical slice treats the mission as not
    eligible and stops before ever touching Runtime.
    """

    def __init__(self, rules_engine: RulesEngine) -> None:
        self.rules_engine = rules_engine

    def is_eligible(self, variables: dict[str, Any]) -> bool:
        rules = self.rules_engine.list_rules()
        if not rules:
            return True
        context = RuleContext(variables=variables)
        results = self.rules_engine.evaluate_all(rules, context)
        return all(result.success for result in results)
