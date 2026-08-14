"""Tests for POST /billing/sales-playbook/action and
GET /billing/sales-playbook/conversion-summary (Sprint 285).

Same usage-tracking wiring as test_sales_playbook.py (Sprint 284) for
the end-to-end "action recorded shows up in the live playbook" scenario.
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


# --- POST /sales-playbook/action ------------------------------------------


def test_action_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": "x", "lead_type": "upgrade_offer", "action": "execute"},
    )

    assert response.status_code == 401


def test_action_usuario_nao_admin_bloqueia():
    client, container = _client()
    token = _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "execute"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_action_execute_registra_contacted():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "execute"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["previous_state"] == "pending"
    assert data["new_state"] == "contacted"
    assert container.auth().get_lead_state(org_a, "upgrade_offer") == "contacted"


def test_action_convert_registra_converted():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "retention_offer", "action": "convert"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.json()["data"]["new_state"] == "converted"


def test_action_lead_type_invalido_retorna_400():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "not-a-real-type", "action": "execute"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


def test_action_invalida_retorna_400():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "not-a-real-action"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


def test_action_organizacao_inexistente_retorna_404():
    client, _ = _client()
    admin_token = _login(client, "admin@test.com", role="admin")

    response = client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": "does-not-exist", "lead_type": "upgrade_offer", "action": "execute"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


def test_action_nao_altera_nenhum_plano_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "convert"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert container.auth().get_organization_plan(org_a) == "free"


def test_action_audita_a_transicao():
    audit = PlatformAudit(storage=None)
    client, container = _client(audit=audit)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "execute"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    events = container.audit.get_events(event="lead_state_transition")
    assert len(events) == 1
    assert events[0]["organization_id"] == org_a
    assert events[0]["metadata"]["lead_type"] == "upgrade_offer"
    assert events[0]["metadata"]["new_state"] == "contacted"


def test_action_reflete_no_playbook_seguinte():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    usage_tracker.increment(org_a, "alerts_sent", amount=460)

    client.post(
        "/api/v1/billing/sales-playbook/action",
        json={"org_id": org_a, "lead_type": "upgrade_offer", "action": "execute"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get(
        "/api/v1/billing/sales-playbook", headers={"Authorization": f"Bearer {admin_token}"}
    )

    entries = [e for e in response.json()["data"]["high_intent"] if e["org_id"] == org_a]
    assert len(entries) == 1
    assert entries[0]["state"] == "contacted"


# --- GET /sales-playbook/conversion-summary -------------------------------


def test_conversion_summary_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/sales-playbook/conversion-summary")

    assert response.status_code == 401


def test_conversion_summary_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/sales-playbook/conversion-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_conversion_summary_admin_recebe_estrutura_correta():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/sales-playbook/conversion-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    summary = response.json()["data"]["summary"]
    assert set(summary.keys()) == {"upgrade_offer", "retention_offer", "expansion_offer"}
    for metrics in summary.values():
        assert set(metrics.keys()) == {
            "pending",
            "contacted",
            "converted",
            "ignored",
            "conversion_rate",
        }


def test_conversion_summary_reflete_acao_registrada():
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
        "/api/v1/billing/sales-playbook/conversion-summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.json()["data"]["summary"]["upgrade_offer"]["converted"] == 1


def test_conversion_summary_audita_o_acesso():
    audit = PlatformAudit(storage=None)
    client, container = _client(audit=audit)
    token = _login(client, "admin@test.com", role="admin")

    client.get(
        "/api/v1/billing/sales-playbook/conversion-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    events = container.audit.get_events(event="conversion_summary_access")
    assert len(events) == 1
