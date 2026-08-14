from app.business_rules.engine.rules_engine import RulesEngine
from app.business_rules.evaluators.comparison_evaluator import ComparisonEvaluator
from app.business_rules.evaluators.expression_evaluator import ExpressionEvaluator
from app.business_rules.evaluators.logical_evaluator import LogicalEvaluator
from app.business_rules.registry.rule_registry import RuleRegistry
from app.business_rules.repositories.rule_repository import RuleRepository


def build_default_rules_engine(
    *, registry: RuleRegistry | None = None, repository: RuleRepository | None = None
) -> RulesEngine:
    """Composition root for this module — registers the three generic
    evaluators (Comparison, Logical, Expression). No specific business rule is
    ever pre-registered here: this engine starts with zero rules, since any
    seeded rule would necessarily encode a domain concept this module must not
    know about.
    """
    return RulesEngine(
        registry=registry or RuleRegistry(),
        repository=repository or RuleRepository(),
        evaluators=[ComparisonEvaluator(), LogicalEvaluator(), ExpressionEvaluator()],
    )
