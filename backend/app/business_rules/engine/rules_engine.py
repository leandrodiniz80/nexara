import time
from typing import Callable, Protocol

from app.business_rules.exceptions.base import RuleError
from app.business_rules.exceptions.rule_exceptions import NoEvaluatorFoundError
from app.business_rules.models.business_rule import BusinessRule
from app.business_rules.models.rule_context import RuleContext
from app.business_rules.models.rule_result import RuleResult
from app.business_rules.registry.rule_registry import RuleRegistry
from app.business_rules.repositories.rule_repository import RuleRepository


class Evaluator(Protocol):
    """Structural contract every registered evaluator satisfies — Comparison,
    Logical, and Expression each implement `supports()`/`evaluate()` by
    convention, never a shared base class, so this Protocol exists purely for
    typing this engine's own `_evaluators` list.
    """

    def supports(self, rule: BusinessRule) -> bool: ...

    def evaluate(
        self,
        rule: BusinessRule,
        context: RuleContext,
        evaluate_child: Callable[[BusinessRule, RuleContext], bool],
    ) -> bool: ...


class RulesEngine:
    """A generic rules engine — it evaluates BusinessRules against a RuleContext
    and reports a RuleResult. It knows nothing about CRM, Workflow, Automation,
    Mission, Prospect, AI, or Runtime: a "rule" here is just field/operator/value
    or a logical combination of other rules, never a specific business concept.
    """

    def __init__(
        self, registry: RuleRegistry, repository: RuleRepository, evaluators: list[Evaluator]
    ) -> None:
        self.registry = registry
        self.repository = repository
        self._evaluators = evaluators

    def register(self, rule: BusinessRule) -> BusinessRule:
        return self.registry.register(rule)

    def list_rules(self) -> list[BusinessRule]:
        return self.registry.list()

    def evaluate(self, rule: BusinessRule, context: RuleContext) -> RuleResult:
        start = time.perf_counter()
        try:
            success = self._evaluate_rule(rule, context)
            reason = None
        except RuleError as exc:
            success = False
            reason = str(exc)
        execution_time = time.perf_counter() - start

        result = RuleResult(
            success=success, rule_name=rule.name, reason=reason, execution_time=execution_time
        )
        self.repository.save_result(result)
        return result

    def evaluate_all(self, rules: list[BusinessRule], context: RuleContext) -> list[RuleResult]:
        return [self.evaluate(rule, context) for rule in rules]

    def evaluate_any(self, rules: list[BusinessRule], context: RuleContext) -> bool:
        return any(result.success for result in self.evaluate_all(rules, context))

    def _evaluate_rule(self, rule: BusinessRule, context: RuleContext) -> bool:
        evaluator = self._find_evaluator(rule)
        return evaluator.evaluate(rule, context, self._evaluate_rule)

    def _find_evaluator(self, rule: BusinessRule) -> Evaluator:
        for evaluator in self._evaluators:
            if evaluator.supports(rule):
                return evaluator
        raise NoEvaluatorFoundError(rule.rule_type)
