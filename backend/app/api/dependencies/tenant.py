from fastapi import Request


def get_request_tenant_id(request: Request) -> str | None:
    """Reads what `TenantMiddleware` already resolved onto `request.state` — the
    per-request-safe counterpart to `Container.get_tenant_id()` (which is
    single-actor-only). Not yet wired into any route: this sprint lays the
    foundation, it doesn't retrofit existing endpoints.
    """
    return getattr(request.state, "tenant_organization_id", None)
