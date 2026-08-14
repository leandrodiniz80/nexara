from typing import TYPE_CHECKING

from app.runtime.exceptions.base import ExecutionRuntimeError

if TYPE_CHECKING:
    from app.runtime.models.enums import ExecutionType


class ExecutorNotFoundError(ExecutionRuntimeError):
    """Raised when RuntimeEngine is asked to run an ExecutionType no registered
    Executor supports."""

    def __init__(self, execution_type: "ExecutionType") -> None:
        self.execution_type = execution_type
        super().__init__(
            f"No Executor registered that supports ExecutionType.{execution_type.name}."
        )


class MissingExecutionRequestError(ExecutionRuntimeError):
    """Raised when an Executor's matching request field (workflow_request,
    automation_request, ...) is missing from the ExecutionContext it was given."""

    def __init__(self, execution_type: "ExecutionType") -> None:
        self.execution_type = execution_type
        super().__init__(
            f"ExecutionContext is missing the request needed for "
            f"ExecutionType.{execution_type.name}."
        )
