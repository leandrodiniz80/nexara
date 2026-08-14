"""Tests for GET /cdn/metrics/alerts/insights (Sprint 261).

Real issues in the spec, fixed here — see cdn.py for the implementation-
level explanation:

1. `_resolve_metrics_scope(session, resolver, container)` — wrong
   argument order and a missing `tenant_id` versus the real signature
   (`_resolve_metrics_scope(session, tenant_id, container, resolver)`,
   Sprint 254); `tenant_id` was never even declared as a dependency on
   the endpoint. Called as written, this raises `TypeError` on every
   request.
2. No `_audit_global_access()` call for the `scope == "global"` case —
   every other `_resolve_metrics_scope()`-consuming endpoint audits a
   cross-tenant admin read (Sprint 255); this one would have been a
   silent gap in that trail.
3. `AlertInsights.__init__(self, store)` (unused) and a pointless
   `hasattr(self, "get_active_incidents")` check (always `True` — it's a
   real method on the class calling it) inside
   `LoaderMetricsStore.get_alert_insights()` — both dead code, removed.
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
        self._strings: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._strings:
            return None
        self._strings[key] = str(value)
        return True

    def delete(self, key):
        self._strings.pop(key, None)
        self._lists.pop(key, None)

    def rpush(self, key, value):
        self._lists.setdefault(key, []).append(value)

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def scan_iter(self, match=None):
        prefix = match.rstrip("*") if match else ""
        return [k for k in list(self._strings) + list(self._lists) if k.startswith(prefix)]


def _storage_with_incidents():
    fake_client = _FakeRedisClient()
    manager = IncidentManager(fake_client)
    storage = AggregatedRedisMetricsStorage(fake_client, incident_manager=manager)
    return storage, manager


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


def test_insights_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/alerts/insights")

    assert res.status_code == 401


def test_insights_sem_incidentes_retorna_estrutura_zerada():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/insights", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "tenant"
    assert body["items"] == {
        "top_domains": [],
        "severity_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "affected_domains": 0,
        "total_incidents": 0,
    }


def test_insights_usuario_comum_ve_apenas_seus_proprios_dominios():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)
    manager.open_or_update("a.com", "error", {"severity": "critical"})
    manager.open_or_update("b.com", "error", {"severity": "high"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts/insights", headers={"Authorization": f"Bearer {token_a}"}
    )

    body = res.json()
    assert body["scope"] == "tenant"
    assert body["items"]["total_incidents"] == 1
    assert body["items"]["top_domains"] == [{"domain": "a.com", "count": 1}]
    assert body["items"]["affected_domains"] == 1


def test_insights_admin_ve_escopo_global_com_todos_os_dominios():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)
    manager.open_or_update("a.com", "error", {"severity": "critical"})
    manager.open_or_update("b.com", "error", {"severity": "high"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts/insights", headers={"Authorization": f"Bearer {admin_token}"}
    )

    body = res.json()
    assert body["scope"] == "global"
    assert body["items"]["total_incidents"] == 2
    assert body["items"]["affected_domains"] == 2
    assert body["items"]["severity_distribution"] == {
        "critical": 1,
        "high": 1,
        "medium": 0,
        "low": 0,
    }


def test_insights_acesso_global_gera_evento_de_auditoria():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/alerts/insights", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.alerts.insights"


def test_insights_acesso_tenant_nao_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.get(
        "/api/v1/cdn/metrics/alerts/insights", headers={"Authorization": f"Bearer {token}"}
    )

    assert container.audit.get_events(event="metrics_global_access") == []


def test_insights_top_domains_ordenado_por_contagem():
    storage, manager = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("busy.com", org_id)
    resolver.register_domain("quiet.com", org_id)
    manager.open_or_update("busy.com", "error", {"severity": "critical"})
    manager.open_or_update("busy.com", "latency", {"severity": "high"})
    manager.open_or_update("quiet.com", "error", {"severity": "medium"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts/insights", headers={"Authorization": f"Bearer {admin_token}"}
    )

    top = res.json()["items"]["top_domains"]
    assert top[0] == {"domain": "busy.com", "count": 2}
