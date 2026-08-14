import uuid

from fastapi import Request

CORRELATION_ID_HEADER = "X-Correlation-ID"


def get_correlation_id(request: Request) -> str:
    """Reads the correlation ID `TracingMiddleware` already resolved onto
    `request.state.correlation_id` (from the client's own X-Correlation-ID header,
    or freshly generated). Recomputes independently only as a defensive fallback —
    in the real app the middleware always runs first, so this branch is untaken.
    """
    existing = getattr(request.state, "correlation_id", None)

    if existing is not None:
        return existing

    return request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
