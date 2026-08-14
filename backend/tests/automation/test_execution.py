import uuid

from app.automation.models.automation_execution import AutomationExecution
from app.automation.models.enums import AutomationStatus
from app.automation.repositories.automation_repository import AutomationRepository


def test_automation_execution_starts_running_by_default():
    execution = AutomationExecution(automation_id=uuid.uuid4())

    assert execution.status == AutomationStatus.RUNNING
    assert execution.finished_at is None
    assert execution.workflow_execution_id is None
    assert execution.warnings == []
    assert execution.errors == []


def test_each_execution_id_is_unique():
    automation_id = uuid.uuid4()

    first = AutomationExecution(automation_id=automation_id)
    second = AutomationExecution(automation_id=automation_id)

    assert first.execution_id != second.execution_id


def test_repository_saves_and_retrieves_by_id():
    repository = AutomationRepository()
    execution = AutomationExecution(automation_id=uuid.uuid4())

    repository.save_execution(execution)

    assert repository.get_execution(execution.execution_id) is execution


def test_repository_get_unknown_id_returns_none():
    repository = AutomationRepository()

    assert repository.get_execution(uuid.uuid4()) is None


def test_repository_list_executions_filters_by_automation_id():
    repository = AutomationRepository()
    automation_a = uuid.uuid4()
    automation_b = uuid.uuid4()
    repository.save_execution(AutomationExecution(automation_id=automation_a))
    repository.save_execution(AutomationExecution(automation_id=automation_a))
    repository.save_execution(AutomationExecution(automation_id=automation_b))

    for_a = repository.list_executions(automation_id=automation_a)

    assert len(for_a) == 2
    assert all(e.automation_id == automation_a for e in for_a)


def test_repository_list_executions_filters_by_status():
    repository = AutomationRepository()
    completed = AutomationExecution(automation_id=uuid.uuid4(), status=AutomationStatus.COMPLETED)
    failed = AutomationExecution(automation_id=uuid.uuid4(), status=AutomationStatus.FAILED)
    repository.save_execution(completed)
    repository.save_execution(failed)

    only_failed = repository.list_executions(status=AutomationStatus.FAILED)

    assert [e.execution_id for e in only_failed] == [failed.execution_id]


def test_repository_list_executions_with_no_filters_returns_everything():
    repository = AutomationRepository()
    repository.save_execution(AutomationExecution(automation_id=uuid.uuid4()))
    repository.save_execution(AutomationExecution(automation_id=uuid.uuid4()))

    assert len(repository.list_executions()) == 2
