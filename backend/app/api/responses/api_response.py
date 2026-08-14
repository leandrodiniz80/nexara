from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.api.responses.error_response import ErrorResponse
from app.application.services.application_service_result import ApplicationServiceResult

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """The one response envelope every route in this API returns — success or
    failure alike. `data` is whatever the route's Application Service call produced;
    HTTP status code is decided by the route (200 vs 4xx) from `success`, never by
    letting an exception propagate.
    """

    success: bool
    data: T | None = None
    errors: list[ErrorResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    request_id: str
    execution_time: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_service_result(
        cls, result: ApplicationServiceResult, *, request_id: str
    ) -> "ApiResponse[T]":
        """Every route builds its ApiResponse this way — the ApplicationServiceResult
        Sprint 14 already produces is 1:1 with everything here except `request_id`/
        `timestamp`, which only the HTTP layer knows about."""
        return cls(
            success=result.success,
            data=result.data,
            errors=[
                ErrorResponse(code="application_error", message=message)
                for message in result.errors
            ],
            warnings=result.warnings,
            request_id=request_id,
            execution_time=result.execution_time,
        )
