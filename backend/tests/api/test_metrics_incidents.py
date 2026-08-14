"""Tests for GET /cdn/metrics/incidents and GET /cdn/metrics/incidents/active.

The most important issue in Sprint 252's own spec, fixed there: its version
read a single flat, unscoped `incident:history` Redis list — shared by
every domain across the entire platform — and returned it to any
authenticated caller with an organization, regardless of which domains
they actually own. That's a real cross-tenant data leak, the same class of
bug already fixed for /metrics/dashboard (Sprint 248) and /metrics/summary
(Sprint 243). History is now written and read per-domain
(IncidentManager.get_history), and this endpoint only ever fetches it for
the domains the caller's own organization owns
(DomainTenantResolver.get_domains_for_organization) — see
incident_manager.py and loader_metrics.py for the implementation-level fix.

The spec's endpoint also reached into `store._storage._client` directly to
get a raw Redis handle — the same encapsulation break already fixed for
debounce (Sprint 251) — replaced here with `store.get_incident_history()`.

Sprint 253 renamed `IncidentManager.process_alert(alert)` to
`open_or_update(domain, type, data)` and added `/metrics/incidents/active`
(currently-open-or-ongoing incidents, as opposed to `/metrics/incidents`'
resolved history) — same tenant-scoping applied to it below.

Sprint 264 added pagination (`page`/`per_page`) and filters
(`severity`/`incident_type`/`domain`) to both endpoints, additive to the
existing `{"items", "total", "scope"}` envelope via a new `meta` field —
not a replacement of it, so every pre-Sprint-264 assertion here (now
updated to also expect `meta`) still holds for the fields it already
checked. `incident_type`, not the spec's own `type`: shadowing the
`type` builtin as a query-param name is a real code smell this codebase
already has an established alternative name for (`alert_type` elsewhere
in this same subsystem). The old `/metrics/incidents?limit=N` query
param is gone, replaced by `page`/`per_page` — nothing in this file ever
exercised `?limit=`, so nothing here needed updating for that removal.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def get(self, key):
        return self._values.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._values:
            return None
        self._values[key] = value
        return True

    def delete(self, key):
        self._values.pop(key, None)

    def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key, start, end):
        values = self._lists.get(key, [])
        self._lists[key] = values[start:] if end == -1 else values[start : end + 1]

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def expire(self, key, ttl):
        return True


def _client(
    storage=None,
) -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    store = LoaderMetricsStore(storage=storage)
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


def test_incidents_endpoint_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/incidents")

    assert res.status_code == 401


def test_incidents_endpoint_sem_dados_retorna_vazio():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "scope": "tenant",
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_incidents_endpoint_storage_padrao_nao_quebra():
    """Default storage (InMemoryMetricsStorage) has no incident_manager at
    all — an honest empty list, not a 500."""
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "scope": "tenant",
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_incidents_endpoint_retorna_apenas_do_proprio_tenant():
    """The actual security fix: an org only ever sees incident history for
    its own domains, even though a resolved incident exists for a domain
    belonging to a different org."""
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, store, resolver = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")
    manager.open_or_update("b.com", "error", {"severity": "critical"})
    manager.resolve("b.com", "error")

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "a.com"

    # Confirms org B independently sees only its own incident, not org A's.
    token_b = client.post(
        "/api/v1/auth/login", json={"email": "owner-b@test.com", "password": "123456"}
    ).json()["data"]["token"]
    res_b = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b.json()["total"] == 1
    assert res_b.json()["items"][0]["domain"] == "b.com"


def test_incidents_endpoint_dominio_nao_registrado_nao_aparece():
    """A resolved incident for a domain nobody has registered to any
    organization is invisible to everyone — there's no owner to scope it
    to, which is the safe default, not a leak."""
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    manager.open_or_update("orphan.com", "error", {"severity": "high"})
    manager.resolve("orphan.com", "error")
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, _, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json() == {
        "items": [],
        "total": 0,
        "scope": "tenant",
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


# --- Sprint 253: GET /metrics/incidents/active --------------------------


def test_incidents_active_endpoint_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/incidents/active")

    assert res.status_code == 401


def test_incidents_active_endpoint_sem_dados_retorna_vazio():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "scope": "tenant",
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_incidents_active_endpoint_retorna_apenas_do_proprio_tenant():
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, _, resolver = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("b.com", "error", {"severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "a.com"


def test_incidents_active_endpoint_nao_inclui_incidentes_resolvidos():
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, _, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json() == {
        "items": [],
        "total": 0,
        "scope": "tenant",
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


def test_incidents_active_endpoint_storage_padrao_nao_quebra():
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "items": [],
        "total": 0,
        "scope": "tenant",
        "meta": {"total": 0, "page": 1, "per_page": 20, "has_next": False},
    }


# --- Sprint 254: RBAC (admin sees history/active incidents globally) ----


def test_incidents_endpoint_admin_ve_historico_global():
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, _, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")
    manager.open_or_update("b.com", "error", {"severity": "critical"})
    manager.resolve("b.com", "error")

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert data["scope"] == "global"
    assert data["total"] == 2
    domains = {item["domain"] for item in data["items"]}
    assert domains == {"a.com", "b.com"}


def test_incidents_endpoint_user_comum_continua_isolado_com_admin_no_sistema():
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, _, resolver = _client(storage)
    _register_admin(client, "admin@test.com")
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")
    manager.open_or_update("b.com", "error", {"severity": "critical"})
    manager.resolve("b.com", "error")

    res = client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["scope"] == "tenant"
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "a.com"


def test_incidents_active_endpoint_admin_ve_ativos_de_todos_os_tenants():
    redis_client = _FakeRedisClient()
    manager = IncidentManager(redis_client)
    storage = AggregatedRedisMetricsStorage(redis_client, incident_manager=manager)
    client, container, _, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("b.com", "error", {"severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/incidents/active", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert data["scope"] == "global"
    assert data["total"] == 2


# --- Sprint 255: global access is audited, tenant access is not ---------


def test_incidents_endpoint_acesso_global_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.incidents"


def test_incidents_endpoint_acesso_tenant_nao_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.get("/api/v1/cdn/metrics/incidents", headers={"Authorization": f"Bearer {token}"})

    assert container.audit.get_events(event="metrics_global_access") == []


def test_incidents_active_endpoint_acesso_global_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/incidents/active",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.incidents.active"
