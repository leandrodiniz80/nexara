from app.business_rules.models.rule_result import RuleResult
from app.business_rules.repositories.rule_repository import RuleRepository


def _result(rule_name: str, success: bool = True) -> RuleResult:
    return RuleResult(success=success, rule_name=rule_name, execution_time=0.001)


def test_save_result_appends_and_returns_it():
    repository = RuleRepository()
    result = _result("score_check")

    saved = repository.save_result(result)

    assert saved is result
    assert repository.list_results() == [result]


def test_list_results_returns_every_saved_result_by_default():
    repository = RuleRepository()
    first = _result("first")
    second = _result("second")
    repository.save_result(first)
    repository.save_result(second)

    results = repository.list_results()

    assert results == [first, second]


def test_list_results_filters_by_rule_name():
    repository = RuleRepository()
    matching = _result("score_check")
    other = _result("city_check")
    repository.save_result(matching)
    repository.save_result(other)

    results = repository.list_results(rule_name="score_check")

    assert results == [matching]


def test_list_results_preserves_multiple_evaluations_of_the_same_rule():
    repository = RuleRepository()
    first = _result("score_check", success=True)
    second = _result("score_check", success=False)
    repository.save_result(first)
    repository.save_result(second)

    results = repository.list_results(rule_name="score_check")

    assert results == [first, second]
