from app.business_rules.builders.rule_builder import RuleBuilder
from app.business_rules.engine.rules_engine import RulesEngine
from app.business_rules.models.enums import ComparisonOperator
from app.business_rules.registry.rule_registry import RuleRegistry
from app.business_rules.repositories.rule_repository import RuleRepository
from app.crm.services.crm_engine_factory import build_default_crm_engine
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.registry.strategy_registry import StrategyRegistry
from app.decision.repositories.decision_repository import DecisionRepository
from app.decision.strategies.recommendation_strategy import RecommendationStrategy
from app.integration.adapters.crm_adapter import CRMAdapter
from app.integration.adapters.decision_adapter import DecisionAdapter
from app.integration.adapters.observability_adapter import ObservabilityAdapter
from app.integration.adapters.rules_adapter import RulesAdapter
from app.observability.services.observability_engine_factory import (
    build_default_observability_engine,
)


def _decision_engine_with_recommendations() -> DecisionEngine:
    engine = DecisionEngine(registry=StrategyRegistry(), repository=DecisionRepository())
    engine.register_strategy(RecommendationStrategy())
    return engine


def test_decision_adapter_returns_the_highest_confidence_workflow():
    adapter = DecisionAdapter(_decision_engine_with_recommendations())

    chosen = adapter.choose_workflow(
        {
            "recommendations": [
                {"name": "Proposal Workflow", "confidence": 0.3},
                {"name": "Prospecting Workflow", "confidence": 0.9},
            ]
        }
    )

    assert chosen == "Prospecting Workflow"


def test_decision_adapter_returns_none_when_nothing_can_be_decided():
    adapter = DecisionAdapter(_decision_engine_with_recommendations())

    assert adapter.choose_workflow({}) is None


def test_rules_adapter_is_eligible_when_no_rules_are_registered():
    engine = RulesEngine(registry=RuleRegistry(), repository=RuleRepository(), evaluators=[])
    adapter = RulesAdapter(engine)

    assert adapter.is_eligible({}) is True


def test_rules_adapter_is_eligible_when_every_registered_rule_passes():
    from app.business_rules.evaluators.comparison_evaluator import ComparisonEvaluator

    engine = RulesEngine(
        registry=RuleRegistry(), repository=RuleRepository(), evaluators=[ComparisonEvaluator()]
    )
    engine.register(
        RuleBuilder.comparison(
            name="score_check",
            field="score",
            operator=ComparisonOperator.GREATER_OR_EQUAL,
            value=70,
        )
    )
    adapter = RulesAdapter(engine)

    assert adapter.is_eligible({"score": 80}) is True


def test_rules_adapter_is_not_eligible_when_a_registered_rule_fails():
    from app.business_rules.evaluators.comparison_evaluator import ComparisonEvaluator

    engine = RulesEngine(
        registry=RuleRegistry(), repository=RuleRepository(), evaluators=[ComparisonEvaluator()]
    )
    engine.register(
        RuleBuilder.comparison(
            name="score_check",
            field="score",
            operator=ComparisonOperator.GREATER_OR_EQUAL,
            value=70,
        )
    )
    adapter = RulesAdapter(engine)

    assert adapter.is_eligible({"score": 40}) is False


def test_crm_adapter_creates_a_company_and_an_opportunity_in_the_default_pipeline():
    adapter = CRMAdapter(build_default_crm_engine())

    opportunity = adapter.create_opportunity(
        company_name="Agência XYZ", opportunity_title="Prospecting - Agência XYZ"
    )

    assert opportunity.title == "Prospecting - Agência XYZ"
    stored = adapter.crm_engine.opportunity_repository.get_opportunity(opportunity.id)
    assert stored is opportunity
    company = adapter.crm_engine.company_repository.get_company(opportunity.company_id)
    assert company.name == "Agência XYZ"


def test_observability_adapter_registers_a_metric():
    engine = build_default_observability_engine()
    adapter = ObservabilityAdapter(engine)

    adapter.record(operation="run_prospecting", execution_time=0.05, success=True)

    metrics = engine.repository.list_metrics(
        component="vertical_slice", operation="run_prospecting"
    )
    assert len(metrics) == 1
    assert metrics[0].execution_time == 0.05
    assert metrics[0].success is True
