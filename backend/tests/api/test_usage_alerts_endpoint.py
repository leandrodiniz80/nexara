"""Tests for GET /tenants/usage/alerts (Sprint 271).

Fixture pattern mirrors test_usage_endpoint.py (Sprint 270). New
registrations default to the "free" plan, whose `alerts_per_hour` limit
is 50 (see PlatformAuth._DEFAULT_PLANS) — used below as the limit these
tests warn/hard-limit against.
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


def test_usage_alerts_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    res = client.get("/api/v1/tenants/usage/alerts")

    assert res.status_code == 401


def test_usage_alerts_sem_usage_tracker_retorna_nulo():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"alerts": None}


def test_usage_alerts_abaixo_do_limite_retorna_nulo():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    usage_tracker.increment(org_id, "alerts_sent", amount=10)

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json() == {"alerts": None}


def test_usage_alerts_em_80_por_cento_retorna_warning():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    usage_tracker.increment(org_id, "alerts_sent", amount=40)

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    body = res.json()["alerts"]
    assert body["level"] == "warning"
    assert body["used"] == 40
    assert body["limit"] == 50
    assert body["message"] is not None


def test_usage_alerts_no_limite_retorna_hard_limit():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    usage_tracker.increment(org_id, "alerts_sent", amount=50)

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    body = res.json()["alerts"]
    assert body["level"] == "hard_limit"
    assert body["used"] == 50
    assert body["limit"] == 50


def test_usage_alerts_plano_enterprise_nunca_alerta():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    container.auth().set_organization_plan(org_id, "enterprise")
    usage_tracker.increment(org_id, "alerts_sent", amount=999_999)

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json() == {"alerts": None}


def test_usage_alerts_e_isolado_por_tenant():
    storage, usage_tracker = _storage_with_usage()
    client, container, _ = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=5)
    usage_tracker.increment(org_b, "alerts_sent", amount=50)

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token_a}"}
    )

    assert res.json() == {"alerts": None}


def test_usage_alerts_sem_organizacao_retorna_404():
    """No public API removes a user's organization membership, so this
    reaches into PlatformAuth's private `_users` dict directly — test
    setup only, not a pattern used in production code."""
    client, container, _ = _client()
    token = _login(client, "owner@test.com")
    container.auth()._users["owner@test.com"]["organization_id"] = None

    res = client.get(
        "/api/v1/tenants/usage/alerts", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 404
