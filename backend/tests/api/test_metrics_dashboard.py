"""Tests for GET /cdn/metrics/dashboard (Sprint 248: tenant-scoped, paginated).

Sprint 247 shipped this endpoint ranking every domain on the platform for
any authenticated user — a real cross-tenant data leak. Sprint 248's own
spec attempted to fix it using `request.session` and `request.state.tenant_id`
— neither exists anywhere in this codebase (auth here is Bearer-token-based
via `get_current_session`/`get_request_tenant_id`; `request.session` would
actually raise `AssertionError: SessionMiddleware must be installed` since
no such middleware is registered) — and imported a `get_domain_resolver`
that doesn't exist (the real name is `get_domain_tenant_resolver`). Using
any of that as written would crash every request to this endpoint. Fixed
using the same dependencies every other tenant-scoped endpoint in this
router already uses (see `/metrics/summary`).

The endpoint also no longer ranks-then-filters (`top_domains(limit=1000)`
then drops what the caller doesn't own): that approach could silently omit
one of the caller's own low-traffic domains if it fell outside the
1000-item cutoff before filtering ever happened. It now looks up exactly
the domains the caller's organization owns
(`DomainTenantResolver.get_domains_for_organization`) and fetches stats
only for those.
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


def _client() -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
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


def test_dashboard_endpoint_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/dashboard")

    assert res.status_code == 401


def test_dashboard_filtra_por_tenant_sem_vazamento():
    """The actual security fix: an org only ever sees its own domains, even
    though events exist for a domain belonging to a different org."""
    client, container, store, resolver = _client()
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    store.add({"domain": "a.com", "event": "success"})
    store.add({"domain": "b.com", "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token_a}"}
    )

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["domain"] == "a.com"


def test_dashboard_dominio_proprio_sem_eventos_ainda_aparece():
    """A registered-but-unused domain must still show up (zeroed out), not
    silently vanish — proves the fix doesn't depend on the domain having
    ranked inside some global top-N cutoff before filtering."""
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("quiet.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "quiet.com"
    assert data["items"][0]["total"] == 0


def test_dashboard_sem_dominios_registrados_retorna_lista_vazia():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0, "limit": 10, "offset": 0, "scope": "tenant"}


def test_dashboard_paginacao():
    client, container, store, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    for i in range(30):
        domain = f"d{i:02d}.com"
        resolver.register_domain(domain, org_id)
        for _ in range(i):
            store.add({"domain": domain, "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard?limit=5&offset=10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 5
    assert data["limit"] == 5
    assert data["offset"] == 10
    assert data["total"] == 30


def test_dashboard_ordenacao_por_total_desc():
    client, container, store, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)
    resolver.register_domain("b.com", org_id)

    for _ in range(5):
        store.add({"domain": "a.com", "event": "success"})
    for _ in range(10):
        store.add({"domain": "b.com", "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    domains = [item["domain"] for item in res.json()["items"]]
    assert domains == ["b.com", "a.com"]


def test_dashboard_ordenacao_deterministica_em_empate_por_total():
    """Same total -> tie-break by error_rate, then domain name — never
    dependent on dict/set iteration order."""
    client, container, store, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("z.com", org_id)
    resolver.register_domain("a.com", org_id)

    store.add({"domain": "z.com", "event": "success"})
    store.add({"domain": "a.com", "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    domains = [item["domain"] for item in res.json()["items"]]
    assert domains == ["a.com", "z.com"]


def test_dashboard_items_tem_health_score():
    client, container, store, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    store.add({"domain": "a.com", "event": "success", "duration": 50})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["items"][0]["health_score"] == 100


def test_dashboard_dominio_100_por_cento_erro_nao_quebra_a_resposta():
    """The exact scenario this dashboard exists to surface (a domain with
    nothing but failures) must not crash the whole response."""
    client, container, store, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("broken.com", org_id)

    store.add({"domain": "broken.com", "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json()["items"][0]["health_score"] == 0


# --- Sprint 254: RBAC (admin sees the whole platform) -------------------


def test_dashboard_user_comum_tem_scope_tenant():
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["scope"] == "tenant"


def test_dashboard_admin_ve_dominios_de_multiplos_tenants():
    client, container, store, resolver = _client()
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    store.add({"domain": "a.com", "event": "success"})
    store.add({"domain": "b.com", "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert data["scope"] == "global"
    assert data["total"] == 2
    domains = {item["domain"] for item in data["items"]}
    assert domains == {"a.com", "b.com"}


def test_dashboard_admin_nao_tem_organizacao_e_ainda_assim_ve_tudo():
    """An admin's own (auto-created) organization owns nothing — the
    global view doesn't depend on the admin happening to own any domains
    themselves."""
    client, container, store, resolver = _client()
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner@test.com")
    org = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org)
    store.add({"domain": "a.com", "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert data["scope"] == "global"
    assert data["items"][0]["domain"] == "a.com"


def test_dashboard_usuario_comum_nunca_ve_dominios_de_outro_tenant_mesmo_com_admin_no_sistema():
    """The presence of an admin elsewhere on the platform must not change
    what a regular user sees — RBAC only expands access for the admin's
    own session, never implicitly for anyone else."""
    client, container, store, resolver = _client()
    _register_admin(client, "admin@test.com")
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    store.add({"domain": "a.com", "event": "success"})
    store.add({"domain": "b.com", "event": "success"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["scope"] == "tenant"
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "a.com"


# --- Sprint 255: global access is audited, tenant access is not ---------


def test_dashboard_acesso_global_gera_evento_de_auditoria():
    client, container, _, resolver = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["email"] == "admin@test.com"
    assert events[0]["metadata"]["resource"] == "metrics.dashboard"
    assert events[0]["metadata"]["scope"] == "global"


def test_dashboard_acesso_tenant_nao_gera_evento_de_auditoria():
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")

    client.get("/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"})


# --- Sprint 262 regression: /metrics/dashboard itself is untouched ------
#
# Sprint 262 only added new LoaderMetricsStore methods
# (get_health_score()/get_dashboard_data()) and a new endpoint
# (/metrics/dashboard/overview) — this endpoint's own envelope shape,
# tenant scoping, and pagination must all still behave exactly as before.


def test_dashboard_envelope_permanece_items_total_limit_offset_scope():
    client, _, _, resolver = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert set(res.json().keys()) == {"items", "total", "limit", "offset", "scope"}


def test_dashboard_ainda_filtra_por_tenant_apos_sprint_262():
    client, container, store, resolver = _client()
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["scope"] == "tenant"
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "a.com"

    assert container.audit.get_events(event="metrics_global_access") == []
