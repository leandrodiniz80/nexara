"""Tests for GET /cdn/metrics/audit.

Real issues in the spec, fixed here — see cdn.py for the implementation-
level explanation:

1. The spec proposed a brand-new, Redis-only `AuditLog` class, separate
   from `PlatformAudit` (already used platform-wide — registration, login,
   plan upgrades, branding changes — and already wired into
   `PlatformContainer` as `container.audit`). Building a second, parallel
   audit system for admin-metrics-access specifically would fragment
   exactly the "who accessed what, when" record this feature exists to
   provide for compliance (SOC2/LGPD) purposes. Reused `PlatformAudit`
   instead — `container.audit.log_event()`/`get_events()` already do
   everything the spec's `AuditLog.log()`/`get_logs()` would have, with
   built-in filtering by event/email/organization_id.
2. `session.role`/`session.organization_id`/`session.user_id` (attribute
   access) — `session` is a plain dict everywhere in this codebase
   (`session["email"]`, etc.); none of those attributes exist on a dict.
   Also, `role` is read fresh via `container.auth().get_user_role(...)`,
   not from the session dict's own (login-time-cached) `role` value — the
   same established pattern already used by `_resolve_metrics_scope()`
   (Sprint 254) and every other admin-gated router in this codebase
   (metrics.py/logs.py/audit.py).
3. `PlatformContainer(bootstrap=PlatformBootstrap())`'s own `audit` param
   defaults to `None` — the *production* dependency (`get_platform_container`
   in `app/api/dependencies/auth.py`) never passed one, so the audit trail
   this whole sprint is about would have been silently inert in the actual
   running app. Fixed at the source (`get_platform_container` now
   constructs a real `PlatformAudit()`), not just in test setup.
4. `if session.role != "admin": return {"items": [], "total": 0}` — silent
   empty response for a non-admin, inconsistent with the pre-existing
   `role != "admin"` gate on `/api/v1/metrics`, `/api/v1/logs` and
   `/api/v1/audit/events` (all unrelated, pre-existing routers), which all
   403. `/metrics/audit` is not a tenant-scoped resource with a legitimate
   "empty" state for non-admins the way `/metrics/dashboard` etc. are —
   it's an admin-only resource, so it 403s instead, matching that
   established precedent.
5. Keyed by the *caller's own* `organization_id` (`audit:log:{org_id}`) —
   for a platform-wide "who accessed cross-tenant data" trail, that means
   each admin would only ever see their own past actions, never a unified
   view across every admin, defeating the point of a compliance audit
   trail. Fixed: the log records each admin's own organization_id for
   traceability, but `/metrics/audit` deliberately does not filter reads
   by it — every admin sees the same, unified, platform-wide log.

Sprint 264 added pagination (`page`/`per_page`, replacing the old
`limit: int = 50` param) via an additive `meta` field alongside the
existing `{"items", "total"}` envelope — every pre-Sprint-264 assertion
here (updated to also expect `meta`) still holds for the fields it
already checked. Also fixes two bugs in that sprint's own spec: it would
have dropped the `event=metrics_global_access` filter entirely (widening
this endpoint to show every audit event type ever logged, not just
cross-tenant admin reads) and called `get_events()` with no `limit`
override (relying on its own default of 100, which would silently starve
any page beyond the first ~100 events even if more genuinely exist).
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore


def _client(with_audit: bool = True) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(
        bootstrap=PlatformBootstrap(), audit=PlatformAudit() if with_audit else None
    )
    store = LoaderMetricsStore()
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container


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


def test_audit_endpoint_sem_autenticacao_bloqueia():
    client, _ = _client()

    res = client.get("/api/v1/cdn/metrics/audit")

    assert res.status_code == 401


def test_audit_endpoint_usuario_comum_bloqueado_com_403():
    """Not the tenant-scoped "empty is valid" pattern used by
    /metrics/dashboard etc. — this is an admin-only resource."""
    client, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get("/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 403


def test_audit_endpoint_admin_ve_logs_vazios_sem_acesso_global_anterior():
    client, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_audit_endpoint_admin_ve_evento_apos_acesso_global():
    client, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
    )

    res = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["email"] == "admin@test.com"
    assert data["items"][0]["metadata"]["resource"] == "metrics.dashboard"
    assert data["items"][0]["metadata"]["role"] == "admin"


def test_audit_endpoint_e_global_nao_filtrado_pela_organizacao_do_chamador():
    """The actual architectural fix: every admin sees the same unified log,
    not just events they themselves triggered under their own org."""
    client, _ = _client()
    admin_a_token = _register_admin(client, "admin-a@test.com")
    admin_b_token = _register_admin(client, "admin-b@test.com")

    client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_a_token}"}
    )
    client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_b_token}"}
    )

    res_a = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_a_token}"}
    )
    res_b = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_b_token}"}
    )

    assert res_a.json()["total"] == 2
    assert res_b.json()["total"] == 2
    emails_a = {item["email"] for item in res_a.json()["items"]}
    assert emails_a == {"admin-a@test.com", "admin-b@test.com"}


def test_audit_endpoint_acesso_tenant_nao_aparece_no_log():
    client, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")
    owner_token = _login(client, "owner@test.com")

    client.get("/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {owner_token}"})

    res = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.json()["total"] == 0


def test_audit_endpoint_sem_platform_audit_configurado_retorna_vazio():
    """container.audit defaults to None on PlatformContainer — must degrade
    gracefully, not 500, matching every other "optional capability" in
    this codebase."""
    client, _ = _client(with_audit=False)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_audit_endpoint_sem_platform_audit_nao_quebra_endpoints_de_metrics():
    """A global metrics read must not fail just because auditing isn't
    configured — auditing a read must never be able to break the read."""
    client, _ = _client(with_audit=False)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
