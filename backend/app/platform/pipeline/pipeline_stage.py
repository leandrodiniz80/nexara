import abc
from typing import Any

from app.platform.orchestration.platform_execution_context import PlatformExecutionContext
from app.platform.session.execution_session import ExecutionSession


class PipelineStage(abc.ABC):
    """The abstract contract every stage of ExecutionPipeline satisfies. A
    stage reads and returns only the generic `state` dict passed through
    it — it never mutates the given ExecutionSession or
    PlatformExecutionContext, and this contract itself knows nothing about
    any specific domain a concrete stage might wrap.
    """

    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    async def execute(
        self,
        session: ExecutionSession,
        context: PlatformExecutionContext,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError
