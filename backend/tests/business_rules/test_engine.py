from app.business_rules.builders.rule_builder import RuleBuilder
from app.business_rules.engine.rules_engine import RulesEngine
from app.business_rules.engine.rules_engine_factory import build_default_rules_engine
from app.business_rules.evaluators.comparison_evaluator import ComparisonEvaluator
from app.business_rules.models.enums import ComparisonOperator, LogicalOperator
from app.business_rules.models.rule_context import RuleContext
from app.business_rules.registry.rule_registry import RuleRegistry
from app.business_rules.repositories.rule_repository import RuleRepository


def test_register_adds_the_rule_to_the_registry_and_list_rules_reflects_it():
    engine = build_default_rules_engine()
    rule = RuleBuilder.comparison(
        name="score_check", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )

    engine.register(rule)

    assert engine.list_rules() == [rule]


def test_evaluate_returns_a_rule_result_with_every_expected_field():
    engine = build_default_rules_engine()
    rule = RuleBuilder.comparison(
        name="score_check", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )

    result = engine.evaluate(rule, RuleContext(variables={"score": 80}))

    assert result.success is True
    assert result.rule_name == "score_check"
    assert result.reason is None
    assert result.execution_time >= 0


def test_evaluate_persists_every_result_in_the_repository():
    engine = build_default_rules_engine()
    rule = RuleBuilder.comparison(
        name="score_check", field="score", operator=ComparisonOperator.EQUALS, value=1
    )

    result = engine.evaluate(rule, RuleContext(variables={"score": 1}))

    assert engine.repository.list_results() == [result]


def test_evaluate_all_evaluates_every_rule_and_returns_one_result_each():
    engine = build_default_rules_engine()
    high_score = RuleBuilder.comparison(
        name="score", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )
    right_city = RuleBuilder.comparison(
        name="city", field="cidade", operator=ComparisonOperator.EQUALS, value="Goiânia"
    )
    context = RuleContext(variables={"score": 50, "cidade": "Goiânia"})

    results = engine.evaluate_all([high_score, right_city], context)

    assert [r.rule_name for r in results] == ["score", "city"]
    assert [r.success for r in results] == [False, True]


def test_evaluate_any_succeeds_if_at_least_one_rule_succeeds():
    engine = build_default_rules_engine()
    a = RuleBuilder.comparison(name="a", field="x", operator=ComparisonOperator.EQUALS, value=1)
    b = RuleBuilder.comparison(name="b", field="y", operator=ComparisonOperator.EQUALS, value=1)

    assert engine.evaluate_any([a, b], RuleContext(variables={"x": 2, "y": 1})) is True
    assert engine.evaluate_any([a, b], RuleContext(variables={"x": 2, "y": 2})) is False


def test_evaluate_wraps_an_unsupported_rule_type_into_a_failed_result_not_a_raise():
    engine = RulesEngine(
        registry=RuleRegistry(), repository=RuleRepository(), evaluators=[ComparisonEvaluator()]
    )
    expression_rule = RuleBuilder.expression(name="unsupported", expression="score >= 70")

    result = engine.evaluate(expression_rule, RuleContext(variables={"score": 80}))

    assert result.success is False
    assert result.rule_name == "unsupported"
    assert "RuleType.EXPRESSION" in result.reason


def test_evaluate_wraps_an_invalid_rule_into_a_failed_result():
    engine = build_default_rules_engine()
    bad_not = RuleBuilder.logical(
        name="bad_not",
        operator=LogicalOperator.NOT,
        rules=[
            RuleBuilder.comparison(
                name="a", field="x", operator=ComparisonOperator.EQUALS, value=1
            ),
            RuleBuilder.comparison(
                name="b", field="y", operator=ComparisonOperator.EQUALS, value=1
            ),
        ],
    )

    result = engine.evaluate(bad_not, RuleContext())

    assert result.success is False
    assert result.reason is not None


def test_rules_engine_never_imports_crm_workflow_automation_runtime_mission_ai_or_platform():
    import app.business_rules.engine.rules_engine as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    for forbidden in (
        "app.crm",
        "app.workflows",
        "app.automation",
        "app.runtime",
        "app.mission",
        "app.ai",
        "app.platform",
        "app.research",
        "app.prospect",
    ):
        assert forbidden not in source
