from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.dependencies.auth import get_platform_container

_BEARER_PREFIX = "Bearer "


class TenantMiddleware(BaseHTTPMiddleware):
    """Extracts the caller's organization_id (from the session behind their bearer
    token, if any) onto `request.state.tenant_organization_id` — deliberately never
    through `Container.set_tenant()`/`_current_token`. Those are single-actor-only
    (safe for one CLI/test/script owning its own Container exclusively); mutating
    them from request-handling code would corrupt state across concurrent requests
    on the shared per-process Container, exactly the class of bug `container.auth()`
    direct-call routes have avoided since the API layer was first built. Reads the
    session read-only via `container.auth().get_session(token)` and stores the
    result on `request.state`, which Starlette already scopes per-request safely.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.tenant_organization_id = None

        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith(_BEARER_PREFIX):
            token = auth_header[len(_BEARER_PREFIX) :]

            resolve_container = request.app.dependency_overrides.get(
                get_platform_container, get_platform_container
            )
            container = resolve_container()

            session = container.auth().get_session(token)

            if session is not None:
                request.state.tenant_organization_id = session.get("organization_id")

        return await call_next(request)
