"""Tests for GET /tenants/usage (Sprint 270).

Real issues in the spec's own router code, fixed here — see tenants.py's
own docstring on this endpoint for the implementation-level explanation:

1. `Depends(get_container)` — no such dependency exists anywhere in this
   codebase; the real name is `get_platform_container`.
2. `container.metrics_store()` — `PlatformContainer` has no such method;
   the metrics store is injected via its own dependency
   (`get_metrics_store`), like every `/cdn/metrics/*` endpoint already
   does.
3. `container.metrics_store()._storage` — reaches past the store into
   its private `_storage`, exactly what this sprint's own rules forbid.
   Fixed via `store.get_usage()`.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage
from app.platform.usage.usage_tracker import UsageTracker


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, str] = {}

    def incrby(self, key, amount):
        self._values[key] = str(int(self._values.get(key, 0)) + amount)
        return int(self._values[key])

    def get(self, key):
        return self._values.get(key)

    def delete(self, key):
        self._values.pop(key, None)


def _storage_with_usage():
    fake_client = _FakeRedisClient()
    usage_tracker = UsageTracker(fake_client)
    storage = AggregatedRedisMetricsStorage(fake_client, usage_tracker=usage_tracker)
    return storage, usage_tracker


def _client(storage=None) -> tuple[TestClient, PlatformContainer, LoaderMetricsStore]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    store = LoaderMetricsStore(storage=storage)
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    return TestClient(app), container, store


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_usage_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    res = client.get("/api/v1/tenants/usage")

    assert res.status_code == 401


def test_usage_sem_usage_tracker_retorna_zero():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get("/api/v1/tenants/usage", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json() == {"usage": {"alerts_sent": 0}}


def test_usage_retorna_contagem_real():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    usage_tracker.increment(org_id, "alerts_sent", amount=7)

    res = client.get("/api/v1/tenants/usage", headers={"Authorization": f"Bearer {token}"})

    assert res.json() == {"usage": {"alerts_sent": 7}}


def test_usage_e_isolado_por_tenant():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=3)
    usage_tracker.increment(org_b, "alerts_sent", amount=99)

    res = client.get("/api/v1/tenants/usage", headers={"Authorization": f"Bearer {token_a}"})

    assert res.json() == {"usage": {"alerts_sent": 3}}
