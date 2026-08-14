from abc import ABC, abstractmethod

from app.runtime.models.enums import ExecutionType
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult


class Executor(ABC):
    """Contract every Executor (WorkflowExecutor, AutomationExecutor, JobExecutor,
    and whatever PIPELINE/AGENT/CUSTOM Executor comes later) must satisfy.
    RuntimeEngine only ever talks to an Executor through this interface — it has no
    idea which concrete Executor it's using, the same Dependency Inversion every
    other Provider/Strategy abstraction in this codebase already relies on.
    """

    @abstractmethod
    def supports(self, execution_type: ExecutionType) -> bool:
        """Whether this Executor knows how to run the given ExecutionType."""

    @abstractmethod
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Run whatever this Executor is for, using `context`'s matching request
        field, and return an ExecutionResult — never raise past this boundary for
        a request that was actually attempted."""
