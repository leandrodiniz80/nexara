from app.runtime.executors.executor import Executor
from app.runtime.models.enums import ExecutionType
from app.runtime.models.execution_context import ExecutionContext
from app.runtime.models.execution_result import ExecutionResult


class JobExecutor(Executor):
    """Registered so ExecutionType.JOB is a recognized type with a real Executor —
    but this sprint builds no integration with app/jobs at all. `supports()` still
    reports True (so RuntimeEngine finds this Executor instead of raising
    ExecutorNotFoundError), and `execute()` raises NotImplementedError rather than
    silently pretending to run something. A future sprint replaces this body, not
    RuntimeEngine's or ExecutorRegistry's public API.
    """

    def supports(self, execution_type: ExecutionType) -> bool:
        return execution_type == ExecutionType.JOB

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        raise NotImplementedError("JobExecutor is infrastructure only — no integration yet.")
