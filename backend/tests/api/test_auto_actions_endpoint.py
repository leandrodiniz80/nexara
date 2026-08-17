"""Tests for GET /tenants/auto-actions and POST /tenants/auto-actions/apply
(Sprint 278).

Real BillingAnalytics.score_organization() can't push a free org's
health score above 85 (see decision_engine.py's own docstrings), so
"upgrade actually happens" here is exercised via usage (over 100% of the
free plan's alerts_per_hour limit, 50), wiring a real UsageTracker
through get_metrics_store the same way test_usage_endpoint.py (Sprint
270) does.
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


def test_get_sem_autenticacao_bloqueia():
    client, _ = _client()

    assert client.get("/api/v1/tenants/auto-actions").status_code == 401


def test_apply_sem_autenticacao_bloqueia():
    client, _ = _client()

    assert client.post("/api/v1/tenants/auto-actions/apply", json={}).status_code == 401


def test_get_membro_comum_sem_organizacao_e_bloqueado():
    """A user with no organization at all is neither admin nor owner."""
    client, container = _client()
    token = _login(client, "user@test.com")
    container.auth().set_user_organization_for_test("user@test.com", None)

    response = client.get(
        "/api/v1/tenants/auto-actions", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_get_retorna_estrutura_correta():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/tenants/auto-actions", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"upgrades", "downgrade_recommendations", "retention"}
    assert isinstance(body["upgrades"], list)
    assert isinstance(body["downgrade_recommendations"], list)
    assert isinstance(body["retention"], list)


def test_get_nao_muta_nada_mesmo_com_upgrade_proposto():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    response = client.get(
        "/api/v1/tenants/auto-actions", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    assert any(a["org_id"] == org_a for a in response.json()["upgrades"])
    # Multiple GETs, still free -- no side effects from a read.
    client.get("/api/v1/tenants/auto-actions", headers={"Authorization": f"Bearer {admin_token}"})
    assert container.auth().get_organization_plan(org_a) == "free"


def test_owner_ve_apenas_a_propria_organizacao():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)
    usage_tracker.increment(org_b, "alerts_sent", amount=51)

    response = client.get(
        "/api/v1/tenants/auto-actions", headers={"Authorization": f"Bearer {token_a}"}
    )

    org_ids = {a["org_id"] for a in response.json()["upgrades"]}
    assert org_a in org_ids
    assert org_b not in org_ids


def test_apply_como_owner_para_outra_org_e_rejeitado():
    client, container = _client()
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")

    response = client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_b},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 403


def test_apply_como_owner_para_propria_org_executa_e_persiste():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    token_a = _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    response = client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["upgrades"]) == 1
    assert body["upgrades"][0]["org_id"] == org_a
    assert container.auth().get_organization_plan(org_a) == "pro"


def test_apply_sem_filtro_afeta_todas_as_organizacoes_elegiveis_admin():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)
    usage_tracker.increment(org_b, "alerts_sent", amount=51)

    response = client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    applied_ids = {a["org_id"] for a in response.json()["upgrades"]}
    assert applied_ids == {org_a, org_b}
    assert container.auth().get_organization_plan(org_a) == "pro"
    assert container.auth().get_organization_plan(org_b) == "pro"


def test_apply_filtro_action_type_restringe_execucao():
    storage, usage_tracker = _storage_with_usage()
    client, container = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    response = client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"action_type": "downgrade"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    body = response.json()
    assert body["upgrades"] == []
    assert container.auth().get_organization_plan(org_a) == "free"


def test_apply_audita_cada_acao_aplicada():
    storage, usage_tracker = _storage_with_usage()
    audit = PlatformAudit(storage=None)
    client, container = _client(storage, audit=audit)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    events = container.audit.get_events(event="billing_auto_action")
    assert len(events) == 1
    assert events[0]["organization_id"] == org_a
    assert events[0]["metadata"]["action"] == "upgrade"
    assert events[0]["metadata"]["from"] == "free"
    assert events[0]["metadata"]["to"] == "pro"
    assert events[0]["metadata"]["reason"] == "over_usage"


def test_apply_sem_acoes_correspondentes_retorna_vazio():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": "does-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "upgrades": [],
        "downgrade_recommendations": [],
        "retention": [],
        "pending_checkout": [],
    }
