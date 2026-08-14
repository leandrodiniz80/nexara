from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.responses.error_response import ErrorResponse
from app.platform.rate_limit.platform_rate_limiter import RateLimitExceeded

_DEFAULT_STATUS = 500


class ExceptionMapper:
    """Turns any exception the API might see into an (HTTP status code,
    ErrorResponse) pair. Every known FastAPI/Starlette exception gets a specific,
    meaningful mapping; anything else falls through to a generic 500 with a message
    that never repeats the exception's own text (which could leak internals) — the
    real exception is for the server log, not the client response.
    """

    @staticmethod
    def map(exc: Exception) -> tuple[int, ErrorResponse]:
        if isinstance(exc, RequestValidationError):
            return 422, ErrorResponse(
                code="validation_error",
                message="The request could not be validated.",
                details=exc.errors(),
            )
        if isinstance(exc, StarletteHTTPException):
            return exc.status_code, ErrorResponse(
                code=_code_for_status(exc.status_code), message=str(exc.detail)
            )
        if isinstance(exc, LookupError):
            return 404, ErrorResponse(code="not_found", message=str(exc))
        if isinstance(exc, RateLimitExceeded):
            return 429, ErrorResponse(code="rate_limit_exceeded", message=str(exc))
        if isinstance(exc, PermissionError):
            return 403, ErrorResponse(code="forbidden", message=str(exc))
        if isinstance(exc, ValueError):
            return 400, ErrorResponse(code="invalid_input", message=str(exc))
        return _DEFAULT_STATUS, ErrorResponse(
            code="internal_error", message="An unexpected error occurred."
        )


def _code_for_status(status_code: int) -> str:
    if status_code == 404:
        return "not_found"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 409:
        return "conflict"
    return "http_error"
