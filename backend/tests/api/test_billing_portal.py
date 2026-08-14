"""Tests for POST /billing/portal (Sprint 280).

Same established override pattern as test_billing_stripe.py (Sprint
269) -- `get_stripe_sync_service` overridden directly with a MagicMock,
rather than exercising the real module-level singleton (which is `None`
unless real STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET env vars are set).
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.billing import get_stripe_sync_service
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client(stripe_sync=None, audit=None) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_stripe_sync_service] = lambda: stripe_sync
    return TestClient(app), container


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_portal_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.post("/api/v1/billing/portal")

    assert response.status_code == 401


def test_portal_cria_sessao_com_sucesso():
    fake_sync = MagicMock()
    fake_sync.create_portal_session.return_value = {
        "status": "portal_created",
        "url": "https://billing.stripe.com/session/xyz",
    }
    client, _ = _client(stripe_sync=fake_sync)
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/portal", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "portal_created"
    assert data["url"] == "https://billing.stripe.com/session/xyz"


def test_portal_passa_org_id_e_return_url_configurado():
    fake_sync = MagicMock()
    fake_sync.create_portal_session.return_value = {"status": "portal_created", "url": "https://x"}
    client, container = _client(stripe_sync=fake_sync)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    client.post("/api/v1/billing/portal", headers={"Authorization": f"Bearer {token}"})

    _, kwargs = fake_sync.create_portal_session.call_args
    assert kwargs["org_id"] == org_id
    assert kwargs["return_url"].startswith("http")


def test_portal_retorna_no_customer_quando_nunca_teve_checkout():
    fake_sync = MagicMock()
    fake_sync.create_portal_session.return_value = {
        "status": "no_customer",
        "reason": "no_stripe_customer",
    }
    client, _ = _client(stripe_sync=fake_sync)
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/portal", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "no_customer"
    assert data["url"] is None


def test_portal_sem_stripe_configurado_retorna_503():
    client, _ = _client(stripe_sync=None)
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/portal", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 503


def test_portal_membro_nao_owner_e_bloqueado():
    fake_sync = MagicMock()
    client, container = _client(stripe_sync=fake_sync)
    _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    container.auth().register_user("member@test.com", "123456", organization_id=org_id)
    member_token = client.post(
        "/api/v1/auth/login", json={"email": "member@test.com", "password": "123456"}
    ).json()["data"]["token"]

    response = client.post(
        "/api/v1/billing/portal", headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403
    fake_sync.create_portal_session.assert_not_called()


def test_portal_audita_a_criacao():
    fake_sync = MagicMock()
    fake_sync.create_portal_session.return_value = {"status": "portal_created", "url": "https://x"}
    audit = PlatformAudit(storage=None)
    client, container = _client(stripe_sync=fake_sync, audit=audit)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    client.post("/api/v1/billing/portal", headers={"Authorization": f"Bearer {token}"})

    events = container.audit.get_events(event="billing_portal_created")
    assert len(events) == 1
    assert events[0]["organization_id"] == org_id
    assert events[0]["metadata"]["status"] == "portal_created"


def test_portal_nao_altera_plano():
    fake_sync = MagicMock()
    fake_sync.create_portal_session.return_value = {"status": "portal_created", "url": "https://x"}
    client, container = _client(stripe_sync=fake_sync)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    client.post("/api/v1/billing/portal", headers={"Authorization": f"Bearer {token}"})

    assert container.auth().get_organization_plan(org_id) == "free"
