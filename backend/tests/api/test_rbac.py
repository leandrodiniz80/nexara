"""Cross-cutting RBAC tests for Sprint 254 (admin vs regular user across
the /cdn/metrics/* endpoints).

Per-endpoint admin/tenant scoping tests live alongside each endpoint's own
test file (test_metrics_dashboard.py, test_metrics_alerts.py,
test_metrics_incidents.py) — this file covers what's shared across all of
them instead: the safe-by-default fallback for anything other than the
exact string "admin", and confirming endpoints Sprint 254 deliberately did
NOT touch (/metrics/summary, /branding/*) aren't accidentally affected by
a caller having role="admin".

Registration-security tests (self-registration can no longer
self-escalate to admin once one exists on the platform) live in
test_auth.py, since that's a fix to `/auth/register` itself, not to
anything in cdn.py — this file assumes that fix is already in place and
only exercises its consequence (role == "admin" being safe to trust for
the cross-tenant view).
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore


def _client() -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    store = LoaderMetricsStore()
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container, store, resolver


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def _register_admin(client: TestClient, email: str) -> str:
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": "123456", "role": "admin"}
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_role_ausente_por_padrao_e_user_nao_admin():
    """Registering without a `role` field at all must default to "user" —
    confirmed at the source (PlatformAuth.register_user's own default) and
    observable via /auth/me, which every RBAC decision in cdn.py ultimately
    reads from (via `get_user_role`)."""
    client, _, _, _ = _client()
    client.post("/api/v1/auth/register", json={"email": "plain@test.com", "password": "123456"})
    token = _login(client, "plain@test.com")

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.json()["data"]["role"] == "user"


def test_role_ausente_tem_escopo_tenant_no_dashboard():
    client, container, _, resolver = _client()
    client.post("/api/v1/auth/register", json={"email": "plain@test.com", "password": "123456"})
    token = _login(client, "plain@test.com")
    org_id = container.auth().get_user_organization("plain@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["scope"] == "tenant"


def test_role_user_explicito_tem_escopo_tenant():
    client, container, _, resolver = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "plain@test.com", "password": "123456", "role": "user"},
    )
    token = _login(client, "plain@test.com")
    org_id = container.auth().get_user_organization("plain@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["scope"] == "tenant"


def test_role_com_valor_arbitrario_nao_vira_admin():
    """Anything other than the exact string "admin" is safe-by-default
    tenant-scoped — a typo or an unrecognized role value must never
    silently grant global access."""
    client, container, _, resolver = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "weird@test.com", "password": "123456", "role": "administrator"},
    )
    token = _login(client, "weird@test.com")
    org_id = container.auth().get_user_organization("weird@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["scope"] == "tenant"


def test_endpoint_nao_tocado_pelo_sprint_254_nao_ganha_acesso_global():
    """/metrics/summary was deliberately not touched by Sprint 254 — an
    admin still can't read another organization's domain summary through
    it just by being an admin; ownership is still required there."""
    client, container, _, resolver = _client()
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/summary?domain=a.com",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 403


def test_metrics_dashboard_ainda_exige_autenticacao_valida():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/dashboard")

    assert res.status_code == 401


def test_endpoint_pre_existente_de_branding_nao_afetado_por_role_admin():
    """A broad sanity check: granting role="admin" for the metrics/incidents
    family must not change unrelated, pre-existing endpoint behavior — an
    admin still only sees branding version history for the organization
    they themselves own (auto-created on registration), same as any owner.
    """
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json()["data"] == []
