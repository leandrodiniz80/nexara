import pytest

from app.business_rules.builders.rule_builder import RuleBuilder
from app.business_rules.engine.rules_engine_factory import build_default_rules_engine
from app.business_rules.exceptions.rule_exceptions import RuleNotFoundError
from app.business_rules.models.enums import ComparisonOperator
from app.business_rules.models.rule_context import RuleContext
from app.business_rules.services.rule_service import RuleService


def test_register_many_registers_every_rule():
    service = RuleService(build_default_rules_engine())
    first = RuleBuilder.comparison(
        name="score_check", field="score", operator=ComparisonOperator.GREATER_OR_EQUAL, value=70
    )
    second = RuleBuilder.comparison(
        name="city_check", field="cidade", operator=ComparisonOperator.EQUALS, value="Goiânia"
    )

    registered = service.register_many([first, second])

    assert registered == [first, second]
    assert {r.name for r in service.engine.list_rules()} == {"score_check", "city_check"}


def test_evaluate_by_name_resolves_the_rule_through_the_engines_registry():
    service = RuleService(build_default_rules_engine())
    service.register_many(
        [
            RuleBuilder.comparison(
                name="score_check",
                field="score",
                operator=ComparisonOperator.GREATER_OR_EQUAL,
                value=70,
            )
        ]
    )

    result = service.evaluate_by_name("score_check", RuleContext(variables={"score": 80}))

    assert result.success is True
    assert result.rule_name == "score_check"


def test_evaluate_by_name_for_an_unregistered_rule_raises():
    service = RuleService(build_default_rules_engine())

    with pytest.raises(RuleNotFoundError):
        service.evaluate_by_name("does-not-exist", RuleContext())


def test_evaluate_all_by_name_evaluates_every_named_rule():
    service = RuleService(build_default_rules_engine())
    service.register_many(
        [
            RuleBuilder.comparison(
                name="score_check", field="score", operator=ComparisonOperator.EQUALS, value=1
            ),
            RuleBuilder.comparison(
                name="city_check", field="cidade", operator=ComparisonOperator.EQUALS, value="X"
            ),
        ]
    )

    results = service.evaluate_all_by_name(
        ["score_check", "city_check"], RuleContext(variables={"score": 1, "cidade": "X"})
    )

    assert [r.success for r in results] == [True, True]
