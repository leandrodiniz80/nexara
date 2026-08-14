"""Tests for GET /cdn/metrics/dashboard/window (Sprint 249: time-windowed
metrics — last_1h/last_24h/last_7d).

Real issues in the spec, fixed here — see metrics_storage.py/loader_metrics.py
for the implementation-level explanation:

1. `add()`'s bucket-writing snippet compared the `event` dict parameter
   directly to the string "success" (`if event == "success":`) instead of
   `event.get("event") == "success"` — always False, so bucketed successes
   would never be recorded at all under the spec's own code.
2. `self.ttl_seconds` doesn't exist on AggregatedRedisMetricsStorage (only
   the separate, non-aggregated RedisMetricsStorage has a ttl); using it as
   written would raise AttributeError on every add().
3. The duration-sum/-count bucket keys were written with no expire() call
   at all (only total/success/error got one) — a real, permanent memory
   leak in Redis.
4. `domains_summary_window()`'s `_health_score(data)` call passed the raw
   per-domain dict *before* `error_rate` was computed and merged in — the
   health score would always see a missing `error_rate`, silently ignoring
   it entirely (only latency would ever move the score, no matter how bad
   the actual error rate).
5. The endpoint itself used the same nonexistent `request.session`/
   `request.state.tenant_id`/`get_domain_resolver` already fixed in Sprint
   248 for the non-windowed dashboard endpoint.
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
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage


class _FakeRedisClient:
    """Minimal in-process double covering incr/incrbyfloat/get/expire/
    pipeline — enough to exercise AggregatedRedisMetricsStorage's real
    bucketed add()/summary_window() through the actual HTTP endpoint."""

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


def test_window_endpoint_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/dashboard/window")

    assert res.status_code == 401


def test_window_endpoint_retorna_window_hours_no_corpo():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window?hours=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["window_hours"] == 1


def test_window_endpoint_default_e_24h():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.json()["window_hours"] == 24


def test_window_endpoint_clampa_hours_absurdo():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window?hours=999999999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["window_hours"] == 24 * 30


def test_window_endpoint_storage_sem_bucket_retorna_zero_honesto():
    """Default storage (InMemoryMetricsStorage) doesn't track events by
    hour at all — a zeroed-out entry per owned domain, not an error."""
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {token}"},
    )

    items = res.json()["items"]
    assert items[0]["domain"] == "a.com"
    assert items[0]["total"] == 0
    assert items[0]["health_score"] == 100


def test_window_endpoint_filtra_por_tenant_com_storage_agregado():
    storage = AggregatedRedisMetricsStorage(_FakeRedisClient())
    client, container, store, resolver = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)

    store.add({"domain": "a.com", "event": "success", "duration": 100})
    store.add({"domain": "b.com", "event": "success", "duration": 100})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "a.com"
    assert data["items"][0]["total"] == 1


def test_window_endpoint_health_score_reflete_erro_na_janela():
    """The bug this guards against: domains_summary_window() computing the
    health score before error_rate was merged into the item, which would
    always score a 100%-error domain as if it had zero errors."""
    storage = AggregatedRedisMetricsStorage(_FakeRedisClient())
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("broken.com", org_id)

    store.add({"domain": "broken.com", "event": "error"})

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {token}"},
    )

    item = res.json()["items"][0]
    assert item["error"] == 1
    assert item["health_score"] == 0


# --- Sprint 254: RBAC (same _resolve_metrics_scope() as /metrics/dashboard) --


def test_window_endpoint_user_comum_tem_scope_tenant():
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.json()["scope"] == "tenant"


def test_window_endpoint_admin_ve_dominios_de_multiplos_tenants():
    storage = AggregatedRedisMetricsStorage(_FakeRedisClient())
    client, container, store, resolver = _client(storage)
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
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    data = res.json()
    assert data["scope"] == "global"
    domains = {item["domain"] for item in data["items"]}
    assert domains == {"a.com", "b.com"}


def test_window_endpoint_acesso_global_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/dashboard/window",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.dashboard.window"
