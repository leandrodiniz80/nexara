import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.api.requests")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Records method, route, status, duration and request_id for every request.
    Runs innermost (registered before RequestIdMiddleware in api_factory.py) so
    `request.state.request_id` is already set by the time it logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        request_id = getattr(request.state, "request_id", None)
        logger.info(
            "%s %s -> %s (%.4fs) request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            request_id,
        )
        return response
