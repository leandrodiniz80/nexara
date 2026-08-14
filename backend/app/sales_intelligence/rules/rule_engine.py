from typing import Any

from pydantic import BaseModel, Field

from app.sales_intelligence.rules.rule import Rule


class RuleEvaluationResult(BaseModel):
    fired_rules: list[str] = Field(default_factory=list)
    effects: dict[str, Any] = Field(default_factory=dict)


class RuleEngine:
    """Runs every registered Rule against a facts dict and combines their effects.

    This is the one piece of logic ScoreCalculator, RecommendationEngine and every
    SalesStrategy share — none of them hardcode "if segment == shopping" anywhere;
    they all just read whichever effect keys they care about out of one
    RuleEvaluationResult.
    """

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules = list(rules) if rules else []

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def evaluate(self, facts: dict[str, Any]) -> RuleEvaluationResult:
        fired: list[str] = []
        effects: dict[str, Any] = {}
        for rule in self.rules:
            effect = rule.evaluate(facts)
            if effect is None:
                continue
            fired.append(rule.name)
            for key, value in effect.items():
                existing = effects.get(key)
                if isinstance(value, (int, float)) and isinstance(existing, (int, float)):
                    effects[key] = existing + value
                else:
                    effects[key] = value
        return RuleEvaluationResult(fired_rules=fired, effects=effects)
