"""Tests for GET /billing/sales-playbook (Sprint 284).

Same usage-tracking wiring as test_revenue_activation.py (Sprint 283)
for the end-to-end high-intent scenario. Test names prefixed with
"sales_playbook_" to avoid colliding with the analogous generic names
already used in test_revenue_activation.py/test_pricing_insights.py.
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


def test_sales_playbook_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/sales-playbook")

    assert response.status_code == 401


def test_sales_playbook_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/sales-playbook", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_sales_playbook_admin_recebe_estrutura_correta():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/sales-playbook", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    for key in ("high_intent", "churn_risk", "expansion"):
        assert isinstance(data[key], list)
        for entry in data[key]:
            # Sprint 285 added "state" alongside these.
            assert set(entry.keys()) == {"org_id", "message", "action", "priority", "state"}


def test_sales_playbook_high_intent_gera_mensagem_personalizada():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    # pro plan's alerts_per_hour limit is 500 -- 460 gives ratio 0.92
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    response = client.get(
        "/api/v1/billing/sales-playbook", headers={"Authorization": f"Bearer {admin_token}"}
    )

    entries = [e for e in response.json()["data"]["high_intent"] if e["org_id"] == org_a]
    assert len(entries) == 1
    assert entries[0]["action"] == "upgrade_offer"
    assert "92%" in entries[0]["message"]


def test_sales_playbook_nao_altera_nenhum_plano_real():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    client.get(
        "/api/v1/billing/sales-playbook", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert container.auth().get_organization_plan(org_a) == "free"


def test_sales_playbook_audita_o_acesso():
    audit = PlatformAudit(storage=None)
    client, container = _client(audit=audit)
    token = _login(client, "admin@test.com", role="admin")

    client.get(
        "/api/v1/billing/sales-playbook", headers={"Authorization": f"Bearer {token}"}
    )

    events = container.audit.get_events(event="sales_playbook_access")
    assert len(events) == 1
