import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

EXECUTION_TIME_HEADER = "X-Execution-Time"


class TimingMiddleware(BaseHTTPMiddleware):
    """Measures real wall-clock time for the whole request (middleware chain +
    route), stores it on `request.state.execution_time`, and echoes it back as a
    response header — independent of whatever execution_time an individual
    ApplicationServiceResult already reports, since this one covers the entire HTTP
    round trip, not just the Application Service call inside it.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        request.state.start_time = start
        response = await call_next(request)
        execution_time = time.perf_counter() - start
        request.state.execution_time = execution_time
        response.headers[EXECUTION_TIME_HEADER] = f"{execution_time:.6f}"
        return response
