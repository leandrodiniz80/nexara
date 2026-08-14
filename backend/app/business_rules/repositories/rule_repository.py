from app.business_rules.models.rule_result import RuleResult


class RuleRepository:
    """In-memory store of every RuleResult produced by RulesEngine.evaluate() —
    no database, no migration was requested for this module. Distinct from
    RuleRegistry: the registry holds "which rules exist", this holds "what
    happened every time one was evaluated".
    """

    def __init__(self) -> None:
        self._results: list[RuleResult] = []

    def save_result(self, result: RuleResult) -> RuleResult:
        self._results.append(result)
        return result

    def list_results(self, *, rule_name: str | None = None) -> list[RuleResult]:
        results = list(self._results)
        if rule_name is not None:
            results = [r for r in results if r.rule_name == rule_name]
        return results
