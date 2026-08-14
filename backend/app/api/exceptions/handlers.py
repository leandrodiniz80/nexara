import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.api.exceptions.mapper import ExceptionMapper
from app.api.responses.api_response import ApiResponse

logger = logging.getLogger("app.api.exceptions")


def _execution_time(request: Request) -> float:
    """TimingMiddleware only stamps request.state.execution_time on the success
    path (after call_next() returns) — on an exception path it never gets that far,
    so we recompute from the same request.state.start_time it also stamps."""
    start_time = getattr(request.state, "start_time", None)
    if start_time is None:
        return 0.0
    return time.perf_counter() - start_time


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


async def _handle(request: Request, exc: Exception) -> JSONResponse:
    status_code, error = ExceptionMapper.map(exc)
    if status_code >= 500:
        # The real exception is for the server log only — ErrorResponse never
        # carries it, per "nunca retornar traceback / nunca retornar exceções
        # Python".
        logger.error(
            "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
        )
    body = ApiResponse(
        success=False,
        data=None,
        errors=[error],
        request_id=_request_id(request),
        execution_time=_execution_time(request),
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def register_exception_handlers(app: FastAPI) -> None:
    """Every exception the API can encounter maps to an ApiResponse-shaped
    JSONResponse through the exact same handler — ExceptionMapper is the only place
    that decides status code/error code, so registering another exception type here
    later never means duplicating response-shaping logic."""
    app.add_exception_handler(RequestValidationError, _handle)
    app.add_exception_handler(StarletteHTTPException, _handle)
    app.add_exception_handler(Exception, _handle)
