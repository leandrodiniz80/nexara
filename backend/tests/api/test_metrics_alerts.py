"""Tests for GET /cdn/metrics/alerts.

Sprint 250 introduced this endpoint; Sprint 251 fixed its baseline
(previously diluted by including the very hour being compared — see
loader_metrics.py) and added debounce. Real issues in Sprint 251's own
spec, fixed here:

1. The endpoint-level issue: unlike every other tenant-scoped endpoint in
   this router (/metrics/summary, /metrics/dashboard,
   /metrics/dashboard/window), the spec's own /metrics/alerts never checked
   `tenant_id is None` or called `ensure_tenant_access(session, tenant_id)`
   — not a crash (a None tenant_id just yields an empty domain list from
   the resolver), but an inconsistency with the defense-in-depth pattern
   every sibling endpoint already follows. The spec also proposed raising
   403 for a missing organization, inconsistent with the 200-plus-empty-
   list pattern the other three /metrics/* endpoints already use for the
   exact same case.
2. Response envelope renamed from {"alerts", "count"} (Sprint 250) to
   {"items", "total"} — a deliberate, spec-requested alignment with
   /metrics/dashboard and /metrics/dashboard/window's shape, not an
   incidental regression; all assertions here use the new shape.
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
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, str] = {}

    def incr(self, key):
        self._values[key] = str(int(self._values.get(key, 0)) + 1)
        return int(self._values[key])

    def incrbyfloat(self, key, amount):
        self._values[key] = str(float(self._values.get(key, 0)) + amount)
        return float(self._values[key])

    def get(self, key):
        return self._values.get(key)

    def expire(self, key, ttl):
        return True

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._values:
            return None

        self._values[key] = value
        return True

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


def _seed_bucket(client: _FakeRedisClient, domain: str, hours_ago: int, total: int, errors: int):
    bucket = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y%m%d%H")
    prefix = f"metrics:{domain}:bucket:{bucket}"
    client._values[f"{prefix}:total"] = str(total)
    client._values[f"{prefix}:success"] = str(total - errors)
    client._values[f"{prefix}:error"] = str(errors)


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


def test_alerts_endpoint_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/alerts")

    assert res.status_code == 401


def test_alerts_endpoint_sem_dados_retorna_vazio():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0, "scope": "tenant"}


def test_alerts_endpoint_filtra_por_tenant():
    fake_client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(fake_client)
    client, container, store, resolver = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("broken-a.com", org_a)
    resolver.register_domain("broken-b.com", org_b)

    for domain in ("broken-a.com", "broken-b.com"):
        for hours_ago in range(1, 24):
            _seed_bucket(fake_client, domain, hours_ago, total=50, errors=0)
        for _ in range(50):
            store.add({"domain": domain, "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "broken-a.com"


def test_alerts_endpoint_ordena_por_severidade():
    fake_client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(fake_client)
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("medium.com", org_id)
    resolver.register_domain("critical.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "medium.com", hours_ago, total=100, errors=0)
        _seed_bucket(fake_client, "critical.com", hours_ago, total=100, errors=0)

    # medium.com: small-ish recent error rate (>0.2, <=0.3).
    for _ in range(75):
        store.add({"domain": "medium.com", "event": "success", "duration": 10})
    for _ in range(25):
        store.add({"domain": "medium.com", "event": "error"})

    # critical.com: overwhelming recent error rate (>0.5).
    for _ in range(90):
        store.add({"domain": "critical.com", "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    domains = [a["domain"] for a in res.json()["items"]]
    assert domains == ["critical.com", "medium.com"]


def test_alerts_endpoint_debounce_impede_repeticao_na_mesma_requisicao_seguinte():
    fake_client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(fake_client)
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "a.com", hours_ago, total=50, errors=0)
    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    first = client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token}"}
    )
    second = client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    assert first.json()["total"] == 1
    assert second.json()["total"] == 0


def test_alerts_endpoint_storage_padrao_nao_quebra():
    """Default storage (InMemoryMetricsStorage) doesn't support
    time-windowing at all — an honest empty alert list, not a 500."""
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0, "scope": "tenant"}


# --- Sprint 254: RBAC (admin sees alerts across every tenant) -----------


def test_alerts_endpoint_admin_ve_alertas_de_todos_os_dominios():
    fake_client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(fake_client)
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("broken-a.com", org_a)
    resolver.register_domain("broken-b.com", org_b)

    for domain in ("broken-a.com", "broken-b.com"):
        for hours_ago in range(1, 24):
            _seed_bucket(fake_client, domain, hours_ago, total=50, errors=0)
        for _ in range(50):
            store.add({"domain": domain, "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = res.json()
    assert data["scope"] == "global"
    domains = {item["domain"] for item in data["items"]}
    assert domains == {"broken-a.com", "broken-b.com"}


def test_alerts_endpoint_user_comum_isolado_mesmo_com_admin_no_sistema():
    fake_client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(fake_client)
    client, container, store, resolver = _client(storage)
    _register_admin(client, "admin@test.com")
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("broken-a.com", org_a)
    resolver.register_domain("broken-b.com", org_b)

    for domain in ("broken-a.com", "broken-b.com"):
        for hours_ago in range(1, 24):
            _seed_bucket(fake_client, domain, hours_ago, total=50, errors=0)
        for _ in range(50):
            store.add({"domain": domain, "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token_a}"}
    )

    data = res.json()
    assert data["scope"] == "tenant"
    domains = {item["domain"] for item in data["items"]}
    assert domains == {"broken-a.com"}


def test_alerts_endpoint_acesso_global_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.alerts"


def test_alerts_endpoint_acesso_tenant_nao_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {token}"})

    assert container.audit.get_events(event="metrics_global_access") == []
