"""Tests for GET /billing/overview (Sprint 286, refined Sprint 287).

Same usage-tracking wiring as test_revenue_activation.py/
test_sales_playbook.py for the end-to-end scenarios.
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


def test_overview_endpoint_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/overview")

    assert response.status_code == 401


def test_overview_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_overview_admin_recebe_estrutura_completa():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data.keys()) == {
        "mrr",
        "active_customers",
        "churn_rate",
        "business_score",
        "business_status",
        "top_opportunities",
        "at_risk_customers",
        "top_customers",
        "conversion_summary",
        "weekly_focus",
        "executive_insight",
    }
    assert 0 <= data["business_score"] <= 100
    assert data["business_status"] in ("growing", "stable", "risk")
    assert isinstance(data["top_opportunities"], list)
    assert isinstance(data["at_risk_customers"], list)
    assert isinstance(data["top_customers"], list)
    assert isinstance(data["executive_insight"], str)
    assert len(data["executive_insight"]) > 0
    assert "message" in data["weekly_focus"]
    assert set(data["conversion_summary"].keys()) == {
        "upgrade_offer",
        "retention_offer",
        "expansion_offer",
    }


def test_overview_mrr_reflete_organizacao_paga_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.json()["data"]["mrr"] == 99


def test_overview_top_opportunities_inclui_priority_score_e_acao():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )

    entries = [e for e in response.json()["data"]["top_opportunities"] if e["org_id"] == org_a]
    assert len(entries) == 1
    assert isinstance(entries[0]["priority_score"], (int, float))
    assert "priority" not in entries[0]
    assert entries[0]["recommended_action"] in ("contact_now", "monitor", "ignore")


def test_overview_at_risk_customers_reflete_churn_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_subscription_status(org_a, "past_due")

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )

    entries = [e for e in response.json()["data"]["at_risk_customers"] if e["org_id"] == org_a]
    assert len(entries) == 1
    assert "priority_score" in entries[0]
    assert "recommended_action" in entries[0]
    assert "revenue_at_risk" in entries[0]


def test_overview_top_customers_reflete_organizacao_paga_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "enterprise")

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )

    entries = [e for e in response.json()["data"]["top_customers"] if e["org_id"] == org_a]
    assert len(entries) == 1
    assert entries[0]["revenue"] == 299
    assert entries[0]["plan"] == "enterprise"


def test_overview_weekly_focus_aponta_para_maior_prioridade():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )

    focus = response.json()["data"]["weekly_focus"]
    assert focus["org_id"] is not None
    assert focus["recommended_action"] in ("contact_now", "monitor", "ignore")


def test_overview_conversion_summary_reflete_acao_registrada():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "convert"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get(
        "/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.json()["data"]["conversion_summary"]["upgrade_offer"]["converted"] == 1


def test_overview_nao_altera_nenhum_plano_real():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    client.get("/api/v1/billing/overview", headers={"Authorization": f"Bearer {admin_token}"})

    assert container.auth().get_organization_plan(org_a) == "free"


def test_overview_audita_o_acesso():
    audit = PlatformAudit(storage=None)
    client, container = _client(audit=audit)
    token = _login(client, "admin@test.com", role="admin")

    client.get("/api/v1/billing/overview", headers={"Authorization": f"Bearer {token}"})

    events = container.audit.get_events(event="business_overview_access")
    assert len(events) == 1
