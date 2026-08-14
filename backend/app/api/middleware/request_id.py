import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Every request gets a UUID — reused from the client's own `X-Request-ID`
    header if it sent one (so a caller can correlate its own logs with ours),
    otherwise generated here. Stored on `request.state.request_id` so every
    downstream middleware/route/exception handler can read it, and always echoed
    back in the response header of the same name.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
