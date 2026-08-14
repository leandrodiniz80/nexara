from app.orchestrator.models.enums import OrchestrationStage
from app.orchestrator.models.orchestration_result import OrchestrationResult
from app.orchestrator.repositories.orchestration_repository import OrchestrationRepository


def _result(success: bool = True) -> OrchestrationResult:
    return OrchestrationResult(
        success=success, stage_reached=OrchestrationStage.COMPLETED, execution_time=0.001
    )


def test_save_result_appends_and_returns_it():
    repository = OrchestrationRepository()
    result = _result()

    saved = repository.save_result(result)

    assert saved is result
    assert repository.list_results() == [result]


def test_list_results_returns_every_saved_result_in_order():
    repository = OrchestrationRepository()
    first = _result(success=True)
    second = _result(success=False)
    repository.save_result(first)
    repository.save_result(second)

    assert repository.list_results() == [first, second]


def test_list_results_returns_a_copy_not_the_internal_list():
    repository = OrchestrationRepository()
    repository.save_result(_result())

    snapshot = repository.list_results()
    snapshot.append(_result())

    assert len(repository.list_results()) == 1
