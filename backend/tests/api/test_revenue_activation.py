"""Tests for GET /billing/revenue-activation (Sprint 283).

Same usage-tracking wiring as test_auto_actions_endpoint.py (Sprint 278)
for the end-to-end high-intent-lead scenario.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.platform.audit.platform_audit import PlatformAudit
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


def _client(storage=None, audit=None) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)
    app.dependency_overrides[get_platform_container] = lambda: container

    if storage is not None:
        store = LoaderMetricsStore(storage=storage)
        app.dependency_overrides[get_metrics_store] = lambda: store

    return TestClient(app), container


def _login(client: TestClient, email: str, role: str = "user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "role": role},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_revenue_activation_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/revenue-activation")

    assert response.status_code == 401


def test_revenue_activation_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/revenue-activation", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_revenue_activation_admin_recebe_estrutura_correta():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/revenue-activation", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data["high_intent"], list)
    assert isinstance(data["churn_risk"], list)
    assert isinstance(data["expansion"], list)


def test_high_intent_reflete_organizacao_real_com_uso_e_saude_altos():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    # pro plan's alerts_per_hour limit is 500 -- above 450 gives ratio > 0.9
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    response = client.get(
        "/api/v1/billing/revenue-activation", headers={"Authorization": f"Bearer {admin_token}"}
    )

    org_ids = [lead["org_id"] for lead in response.json()["data"]["high_intent"]]
    assert org_a in org_ids


def test_expansion_reflete_organizacao_free_com_uso_alto():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    response = client.get(
        "/api/v1/billing/revenue-activation", headers={"Authorization": f"Bearer {admin_token}"}
    )

    org_ids = [lead["org_id"] for lead in response.json()["data"]["expansion"]]
    assert org_a in org_ids


def test_revenue_activation_nao_altera_nenhum_plano_real():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    client.get(
        "/api/v1/billing/revenue-activation", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert container.auth().get_organization_plan(org_a) == "free"


def test_revenue_activation_audita_o_acesso():
    audit = PlatformAudit(storage=None)
    client, container = _client(audit=audit)
    token = _login(client, "admin@test.com", role="admin")

    client.get(
        "/api/v1/billing/revenue-activation", headers={"Authorization": f"Bearer {token}"}
    )

    events = container.audit.get_events(event="revenue_activation_access")
    assert len(events) == 1
