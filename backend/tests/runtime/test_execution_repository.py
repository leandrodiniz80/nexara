import uuid

from app.runtime.models.enums import ExecutionStatus, ExecutionType
from app.runtime.models.execution import Execution
from app.runtime.repositories.execution_repository import ExecutionRepository


def test_save_and_get_execution_round_trip():
    repository = ExecutionRepository()
    execution = Execution(execution_type=ExecutionType.WORKFLOW)

    repository.save_execution(execution)

    assert repository.get_execution(execution.id) is execution


def test_get_execution_for_unknown_id_returns_none():
    repository = ExecutionRepository()

    assert repository.get_execution(uuid.uuid4()) is None


def test_save_execution_overwrites_the_same_id_in_place():
    repository = ExecutionRepository()
    execution = Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.CREATED)
    repository.save_execution(execution)

    execution.status = ExecutionStatus.SUCCESS
    repository.save_execution(execution)

    assert repository.get_execution(execution.id).status == ExecutionStatus.SUCCESS


def test_list_executions_returns_everything_by_default():
    repository = ExecutionRepository()
    workflow_execution = Execution(execution_type=ExecutionType.WORKFLOW)
    automation_execution = Execution(execution_type=ExecutionType.AUTOMATION)
    repository.save_execution(workflow_execution)
    repository.save_execution(automation_execution)

    executions = repository.list_executions()

    assert {e.id for e in executions} == {workflow_execution.id, automation_execution.id}


def test_list_executions_filters_by_execution_type():
    repository = ExecutionRepository()
    workflow_execution = Execution(execution_type=ExecutionType.WORKFLOW)
    automation_execution = Execution(execution_type=ExecutionType.AUTOMATION)
    repository.save_execution(workflow_execution)
    repository.save_execution(automation_execution)

    executions = repository.list_executions(execution_type=ExecutionType.WORKFLOW)

    assert [e.id for e in executions] == [workflow_execution.id]


def test_list_executions_filters_by_status():
    repository = ExecutionRepository()
    running = Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.RUNNING)
    success = Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.SUCCESS)
    repository.save_execution(running)
    repository.save_execution(success)

    executions = repository.list_executions(status=ExecutionStatus.SUCCESS)

    assert [e.id for e in executions] == [success.id]


def test_list_executions_combines_both_filters():
    repository = ExecutionRepository()
    match = Execution(execution_type=ExecutionType.AUTOMATION, status=ExecutionStatus.FAILED)
    wrong_type = Execution(execution_type=ExecutionType.WORKFLOW, status=ExecutionStatus.FAILED)
    wrong_status = Execution(
        execution_type=ExecutionType.AUTOMATION, status=ExecutionStatus.SUCCESS
    )
    repository.save_execution(match)
    repository.save_execution(wrong_type)
    repository.save_execution(wrong_status)

    executions = repository.list_executions(
        execution_type=ExecutionType.AUTOMATION, status=ExecutionStatus.FAILED
    )

    assert [e.id for e in executions] == [match.id]
