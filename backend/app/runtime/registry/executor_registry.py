from app.runtime.exceptions.runtime_exceptions import ExecutorNotFoundError
from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionType


class ExecutorRegistry:
    """Holds every registered Executor and finds the one that supports a given
    ExecutionType — a plain list, checked via each Executor's own `supports()`,
    rather than a `{ExecutionType: Executor}` dict, so an Executor could (in
    principle) support more than one ExecutionType without the registry caring.
    """

    def __init__(self) -> None:
        self._executors: list[Executor] = []

    def register(self, executor: Executor) -> Executor:
        self._executors.append(executor)
        return executor

    def get(self, execution_type: ExecutionType) -> Executor:
        for executor in self._executors:
            if executor.supports(execution_type):
                return executor
        raise ExecutorNotFoundError(execution_type)

    def list(self) -> list[Executor]:
        return list(self._executors)
