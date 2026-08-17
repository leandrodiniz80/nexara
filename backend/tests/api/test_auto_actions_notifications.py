"""Tests for BillingDecisionEngine's Sprint 281 notification hooks, as
exercised through the real API endpoints (POST /tenants/auto-actions/apply,
GET /tenants/auto-actions).

Same usage-tracking wiring as test_auto_actions_endpoint.py (Sprint 278),
plus `get_notification_service` overridden with a recording fake.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.billing import get_notification_service
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


class RecordingNotifier:
    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def send(self, org_id: str, notification_type: str, payload: dict) -> dict:
        self.calls.append((org_id, notification_type, payload))
        return {"sent": True, "type": notification_type, "org_id": org_id}


def _storage_with_usage():
    fake_client = _FakeRedisClient()
    usage_tracker = UsageTracker(fake_client)
    storage = AggregatedRedisMetricsStorage(fake_client, usage_tracker=usage_tracker)
    return storage, usage_tracker


def _client(
    storage=None, notifier=None
) -> tuple[TestClient, PlatformContainer, RecordingNotifier]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    app.dependency_overrides[get_platform_container] = lambda: container

    if storage is not None:
        store = LoaderMetricsStore(storage=storage)
        app.dependency_overrides[get_metrics_store] = lambda: store

    notifier = notifier if notifier is not None else RecordingNotifier()
    app.dependency_overrides[get_notification_service] = lambda: notifier

    return TestClient(app), container, notifier


def _login(client: TestClient, email: str, role: str = "user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "role": role},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_notificacao_disparada_em_upgrade_aplicado():
    storage, usage_tracker = _storage_with_usage()
    client, container, notifier = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert len(notifier.calls) == 1
    assert notifier.calls[0][0] == org_a
    assert notifier.calls[0][1] == "upgrade_recommended"


def test_notificacao_nao_disparada_em_dry_run():
    storage, usage_tracker = _storage_with_usage()
    client, container, notifier = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    client.get(
        "/api/v1/tenants/auto-actions", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert notifier.calls == []


def test_notificacao_nao_disparada_quando_nao_aplicavel():
    """No organization qualifies for anything -- no calls at all."""
    client, _, notifier = _client()
    admin_token = _login(client, "admin@test.com", role="admin")

    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert notifier.calls == []


def test_notificacao_nao_disparada_para_downgrade_recommendations():
    client, container, notifier = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    org = container.auth().get_organization(org_a)
    container.auth().set_organization_created_at(org_a, org["created_at"] - 40 * 86400)

    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert notifier.calls == []


def test_notificacao_nao_duplicada_em_chamadas_repetidas():
    """A second apply() call for the same org, after the first already
    succeeded, doesn't fire a second notification -- the org no longer
    qualifies as a candidate once its plan actually changed."""
    storage, usage_tracker = _storage_with_usage()
    client, container, notifier = _client(storage)
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    usage_tracker.increment(org_a, "alerts_sent", amount=51)

    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert len(notifier.calls) == 1


def test_notificacao_disparada_para_churn_risk():
    client, container, notifier = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_subscription_status(org_a, "past_due")

    client.post(
        "/api/v1/tenants/auto-actions/apply",
        json={"org_id": org_a, "action_type": "retention_flag"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert len(notifier.calls) == 1
    assert notifier.calls[0][1] == "churn_risk"
