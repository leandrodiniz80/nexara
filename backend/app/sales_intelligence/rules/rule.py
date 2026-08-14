from typing import Any, Callable


class Rule:
    """One IF-condition / THEN-effect unit.

    `condition` receives a flat `facts` dict (a CommercialProfile's own fields, plus
    whatever extra ad-hoc context the caller supplied — e.g. a city name that isn't
    part of CommercialProfile itself); `effect` is a dict of adjustments applied only
    when the condition matches, e.g. {"visibility_score": 10} or {"priority": "high"}.
    Numeric effects are summed across every rule that fires; non-numeric effects
    (like "priority") are last-write-wins — see RuleEngine.evaluate().
    """

    def __init__(
        self, name: str, condition: Callable[[dict[str, Any]], bool], effect: dict[str, Any]
    ) -> None:
        self.name = name
        self.condition = condition
        self.effect = effect

    def evaluate(self, facts: dict[str, Any]) -> dict[str, Any] | None:
        return dict(self.effect) if self.condition(facts) else None
