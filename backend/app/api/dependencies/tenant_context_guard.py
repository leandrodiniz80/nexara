def ensure_tenant_access(session: dict, tenant_id: str) -> None:
    """Defense-in-depth: `tenant_id` (resolved by `TenantMiddleware` from the same
    token) should always equal the session's own `organization_id` — both derive
    from the identical `container.auth().get_session(token)` lookup. This exists to
    catch the two ever diverging (e.g. a future change to how one of them parses
    the Authorization header) rather than to handle an expected case.
    """
    if session.get("organization_id") != tenant_id:
        raise PermissionError("Cross-tenant access denied")
