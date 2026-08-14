"""Tests for GET /cdn/metrics/dashboard/overview (Sprint 262).

Real issues in the spec, fixed here — see cdn.py/loader_metrics.py for
the implementation-level explanation:

1. `_resolve_metrics_scope(session, resolver, container)` — wrong
   argument order and a missing `tenant_id`, the same bug already fixed
   for `/metrics/alerts/insights` (Sprint 261). `TypeError` on every call
   as written.
2. `_audit_global_access(container, session, resource=...)` — missing 2
   of its 5 required arguments (`tenant_id`, `role`). `TypeError` on
   every admin/global call as written.
3. `self._storage.summary(domains)` inside `get_dashboard_data()` — a
   *list* passed where `AggregatedRedisMetricsStorage.summary()` expects
   a single domain string or `None`; silently produces a garbage Redis
   key (always zeroed) or, for an empty domains list, falls through to
   the platform-wide global key — a real cross-tenant leak for a caller
   with no organization. Fixed by reusing the already-correct
   `self.summary()` (no args, the same "platform-wide total" behavior
   `/metrics/summary` has always had for any authenticated caller).
4. `get_health_score()` called from inside `get_dashboard_data()`, which
   *itself* recomputes `get_alert_insights()` (and therefore
   `get_active_incidents()`) a second time for the same request — the
   sprint's own "DO NOT compute alerts again" rule, broken by its own
   code. Fixed via `_health_score_from_insights()`, reusing the
   `insights` `get_dashboard_data()` already computed once.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.alert_digest import AlertDigestManager
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage


class _FakeRedisClient:
    def __init__(self):
        self._strings: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def incr(self, key):
        self._strings[key] = str(int(self._strings.get(key, 0)) + 1)
        return int(self._strings[key])

    def incrbyfloat(self, key, amount):
        self._strings[key] = str(float(self._strings.get(key, 0)) + amount)
        return float(self._strings[key])

    def expire(self, key, ttl):
        return True

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

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, client):
        self._client = client
        self._queued: list[tuple[str, tuple]] = []

    def __getattr__(self, name):
        def queue(*args):
            self._queued.append((name, args))
            return self

        return queue

    def execute(self):
        results = [getattr(self._client, name)(*args) for name, args in self._queued]
        self._queued = []
        return results


def _storage_with_everything():
    fake_client = _FakeRedisClient()
    manager = IncidentManager(fake_client)
    digest = AlertDigestManager(fake_client)
    storage = AggregatedRedisMetricsStorage(
        fake_client, incident_manager=manager, alert_digest=digest
    )
    return storage, manager, digest, fake_client


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


def test_overview_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/dashboard/overview")

    assert res.status_code == 401


def test_overview_tenant_scope_sem_dados_retorna_estrutura_zerada():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "tenant"
    assert body["items"]["insights"]["total_incidents"] == 0
    assert body["items"]["digest"] == {"pending": 0}
    assert body["items"]["health_score"] == 100
    assert body["items"]["summary"] is not None


def test_overview_admin_ve_escopo_global():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json()["scope"] == "global"


def test_overview_admin_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/dashboard/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.dashboard.overview"


def test_overview_tenant_scope_nao_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.get(
        "/api/v1/cdn/metrics/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert container.audit.get_events(event="metrics_global_access") == []


def test_overview_health_score_reflete_incidentes_ativos():
    storage, manager, _, _ = _storage_with_everything()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("broken.com", org_id)
    manager.open_or_update("broken.com", "error", {"severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )

    body = res.json()
    assert body["items"]["insights"]["total_incidents"] == 1
    # 100 - (1 critical * weight 5) == 95
    assert body["items"]["health_score"] == 95


def test_overview_digest_reflete_pendencias_do_proprio_tenant():
    storage, _, digest, _ = _storage_with_everything()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    digest.add(org_id, {"domain": "a.com", "severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["items"]["digest"] == {"pending": 1}


def test_overview_digest_zero_para_escopo_global():
    """No single tenant's digest to report for an admin/global overview —
    the digest count stays 0 rather than an arbitrary tenant's."""
    storage, _, digest, _ = _storage_with_everything()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    digest.add(org_id, {"domain": "a.com", "severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.json()["items"]["digest"] == {"pending": 0}


def test_overview_summary_reflete_trafego_agregado():
    storage, _, _, fake_client = _storage_with_everything()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)
    store.add({"domain": "a.com", "event": "success", "duration": 100})
    store.add({"domain": "a.com", "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/overview", headers={"Authorization": f"Bearer {token}"}
    )

    summary = res.json()["items"]["summary"]
    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["error"] == 1
