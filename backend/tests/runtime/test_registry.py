import pytest

from app.runtime.exceptions.runtime_exceptions import ExecutorNotFoundError
from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionType
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult
from app.runtime.registry.executor_registry import ExecutorRegistry


class _FakeExecutor(Executor):
    """Supports exactly one ExecutionType, chosen at construction time — enough to
    exercise ExecutorRegistry's dispatch without any real Workflow/Automation
    engine involved."""

    def __init__(self, execution_type: ExecutionType) -> None:
        self.execution_type = execution_type
        self.calls: list[ExecutionContext] = []

    def supports(self, execution_type: ExecutionType) -> bool:
        return execution_type == self.execution_type

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        self.calls.append(context)
        raise NotImplementedError


def test_register_returns_the_same_executor():
    registry = ExecutorRegistry()
    executor = _FakeExecutor(ExecutionType.WORKFLOW)

    assert registry.register(executor) is executor


def test_get_returns_the_executor_that_supports_the_type():
    registry = ExecutorRegistry()
    workflow_executor = _FakeExecutor(ExecutionType.WORKFLOW)
    automation_executor = _FakeExecutor(ExecutionType.AUTOMATION)
    registry.register(workflow_executor)
    registry.register(automation_executor)

    assert registry.get(ExecutionType.WORKFLOW) is workflow_executor
    assert registry.get(ExecutionType.AUTOMATION) is automation_executor


def test_get_for_an_unsupported_type_raises_executor_not_found():
    registry = ExecutorRegistry()
    registry.register(_FakeExecutor(ExecutionType.WORKFLOW))

    with pytest.raises(ExecutorNotFoundError):
        registry.get(ExecutionType.JOB)


def test_get_on_an_empty_registry_raises_executor_not_found():
    registry = ExecutorRegistry()

    with pytest.raises(ExecutorNotFoundError):
        registry.get(ExecutionType.WORKFLOW)


def test_get_returns_the_first_registered_executor_that_supports_the_type():
    registry = ExecutorRegistry()
    first = _FakeExecutor(ExecutionType.WORKFLOW)
    second = _FakeExecutor(ExecutionType.WORKFLOW)
    registry.register(first)
    registry.register(second)

    assert registry.get(ExecutionType.WORKFLOW) is first


def test_list_returns_every_registered_executor_in_order():
    registry = ExecutorRegistry()
    first = _FakeExecutor(ExecutionType.WORKFLOW)
    second = _FakeExecutor(ExecutionType.AUTOMATION)
    registry.register(first)
    registry.register(second)

    assert registry.list() == [first, second]


def test_list_returns_a_copy_not_the_internal_list():
    registry = ExecutorRegistry()
    registry.register(_FakeExecutor(ExecutionType.WORKFLOW))

    snapshot = registry.list()
    snapshot.append(_FakeExecutor(ExecutionType.AUTOMATION))

    assert len(registry.list()) == 1
