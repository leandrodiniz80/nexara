import time
from typing import Any, Awaitable, Callable, ClassVar

from app.application.services.application_service_result import ApplicationServiceResult


class BaseApplicationService:
    """Standardizes error handling, execution timing, logging and return shape for
    every Application Service — the same template every execution boundary in this
    codebase already follows (AgentBase.execute(), TaskExecutor.run(), JobEngine's
    lifecycle methods): time it, run it, catch anything it raises, always hand back
    a result object instead of letting an exception escape.

    Concrete services never construct ApplicationServiceResult by hand — every public
    method wraps its body in `self._run(operation, func)`.
    """

    service_name: ClassVar[str] = "application_service"

    def __init__(self) -> None:
        self._execution_logs: list[str] = []

    async def _run(
        self, operation: str, func: Callable[[], Awaitable[Any]]
    ) -> ApplicationServiceResult:
        start = time.perf_counter()
        try:
            data = await func()
            execution_time = time.perf_counter() - start
            self._log(f"{self.service_name}.{operation}: succeeded in {execution_time:.4f}s")
            return ApplicationServiceResult(success=True, data=data, execution_time=execution_time)
        except Exception as exc:  # an Application Service must never raise past this boundary
            execution_time = time.perf_counter() - start
            self._log(f"{self.service_name}.{operation}: failed - {exc}")
            return ApplicationServiceResult(
                success=False, errors=[str(exc)], execution_time=execution_time
            )

    def _log(self, message: str) -> None:
        self._execution_logs.append(message)

    def list_execution_logs(self) -> list[str]:
        return list(self._execution_logs)
