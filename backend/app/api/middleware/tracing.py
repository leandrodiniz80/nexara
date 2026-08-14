import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.dependencies.auth import get_platform_container

CORRELATION_ID_HEADER = "X-Correlation-ID"


class TracingMiddleware(BaseHTTPMiddleware):
    """Establishes the request's correlation ID on `request.state.correlation_id`
    before anything downstream runs (reused from the client's own X-Correlation-ID
    header, or freshly generated) — so `get_correlation_id()` and every log call
    made while handling the request agree on the same value. Once the response
    comes back, logs one "http.request" trace entry (method/path/status/duration)
    through the resolved container's PlatformLogger — entirely a no-op if no logger
    is configured, same opt-in contract as audit/metrics/cache/storage.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        response.headers[CORRELATION_ID_HEADER] = correlation_id

        # Respect test-time `app.dependency_overrides` the same way FastAPI's own
        # Depends() resolution would — middleware sits outside that machinery, so
        # this is resolved by hand instead of via Depends(get_platform_container).
        resolve_container = request.app.dependency_overrides.get(
            get_platform_container, get_platform_container
        )
        container = resolve_container()

        if container.logger is not None:
            container.logger.log(
                "INFO",
                "http.request",
                correlation_id=correlation_id,
                metadata={
                    "duration": duration,
                    "path": request.url.path,
                    "status": response.status_code,
                },
            )

        return response
