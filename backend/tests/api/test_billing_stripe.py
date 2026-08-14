from unittest.mock import MagicMock

import stripe
from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.billing import get_stripe_service
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client(stripe_service=None) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_stripe_service] = lambda: stripe_service
    return TestClient(app), container


def _login(client: TestClient, email: str, organization_id: str | None = None) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "organization_id": organization_id},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_upgrade_sem_stripe_configurado_mantem_fluxo_antigo():
    client, container = _client(stripe_service=None)
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["checkout_url"] is None

    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {token}"}
    )
    assert plan_response.json()["data"]["plan"] == "pro"


def test_upgrade_com_stripe_retorna_checkout_url_sem_aplicar_upgrade_ainda():
    fake_service = MagicMock()
    fake_service.create_checkout_session.return_value = "https://checkout.stripe.com/pay/cs_abc"

    client, container = _client(stripe_service=fake_service)
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["checkout_url"] == "https://checkout.stripe.com/pay/cs_abc"

    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {token}"}
    )
    assert plan_response.json()["data"]["plan"] == "free"


def test_upgrade_com_stripe_ainda_exige_owner():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)

    owner_token = _login(client, "owner@test.com")
    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    member_token = _login(client, "member@test.com", organization_id=org_id)

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 403
    fake_service.create_checkout_session.assert_not_called()


def test_upgrade_com_stripe_plano_invalido_retorna_400():
    fake_service = MagicMock()
    fake_service.create_checkout_session.side_effect = ValueError(
        "No Stripe price configured for plan 'ghost'"
    )

    client, container = _client(stripe_service=fake_service)
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "ghost"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_webhook_aplica_upgrade():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")

    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    fake_service.handle_webhook.return_value = {
        "event_type": "checkout.session.completed",
        "org_id": org_id,
        "plan": "pro",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
    }

    response = client.post(
        "/api/v1/billing/webhook",
        content=b'{"fake": "payload"}',
        headers={"stripe-signature": "sig_test"},
    )

    assert response.status_code == 200

    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert plan_response.json()["data"]["plan"] == "pro"
    assert container.auth().get_stripe_ids(org_id) == {
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
    }


def test_webhook_registra_evento_de_auditoria():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")

    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    fake_service.handle_webhook.return_value = {
        "event_type": "checkout.session.completed",
        "org_id": org_id,
        "plan": "pro",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
    }

    client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    events = container.audit.get_events(event="plan_upgraded")
    assert any(
        e["metadata"].get("source") == "stripe"
        and e["metadata"].get("type") == "checkout.session.completed"
        for e in events
    )


def test_webhook_evento_irrelevante_nao_altera_plano():
    fake_service = MagicMock()
    fake_service.handle_webhook.return_value = None
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 200

    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert plan_response.json()["data"]["plan"] == "free"


def test_webhook_sem_stripe_configurado_retorna_503():
    client, container = _client(stripe_service=None)

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 503


def test_webhook_assinatura_invalida_retorna_400():
    fake_service = MagicMock()
    fake_service.handle_webhook.side_effect = stripe.error.SignatureVerificationError(
        "bad signature", "sig_test"
    )
    client, container = _client(stripe_service=fake_service)

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"}
    )

    assert response.status_code == 400


def test_webhook_nao_exige_autenticacao():
    fake_service = MagicMock()
    fake_service.handle_webhook.return_value = None
    client, container = _client(stripe_service=fake_service)

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code != 401


def test_webhook_e_idempotente_do_ponto_de_vista_do_endpoint():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")
    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]

    # first delivery: service reports a new event
    fake_service.handle_webhook.return_value = {
        "event_type": "checkout.session.completed",
        "org_id": org_id,
        "plan": "pro",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
    }
    client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    # retry: service itself now reports the event as already processed
    fake_service.handle_webhook.return_value = None
    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 200

    events = container.audit.get_events(event="plan_upgraded")
    assert len(events) == 1


# --- Sprint 269: invoice.payment_failed / subscription.deleted/updated ---


def test_webhook_payment_failed_marca_status_sem_mudar_plano():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")
    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    container.auth().set_stripe_ids(org_id, "cus_123", "sub_123")
    fake_service.handle_webhook.return_value = {
        "event_type": "invoice.payment_failed",
        "stripe_customer_id": "cus_123",
        "subscription_status": "past_due",
    }

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 200
    assert container.auth().get_subscription_status(org_id) == "past_due"
    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert plan_response.json()["data"]["plan"] == "free"

    events = container.audit.get_events(event="subscription_payment_failed")
    assert len(events) == 1
    assert events[0]["organization_id"] == org_id


def test_webhook_subscription_deleted_reverte_para_free():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")
    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    container.auth().set_organization_plan(org_id, "pro")
    container.auth().set_stripe_ids(org_id, "cus_123", "sub_123")
    fake_service.handle_webhook.return_value = {
        "event_type": "customer.subscription.deleted",
        "stripe_customer_id": "cus_123",
        "subscription_status": "canceled",
        "plan": "free",
    }

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 200
    assert container.auth().get_subscription_status(org_id) == "canceled"
    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert plan_response.json()["data"]["plan"] == "free"

    events = container.audit.get_events(event="subscription_canceled")
    assert len(events) == 1


def test_webhook_resolve_organizacao_pelo_customer_id_quando_sem_metadata():
    """Events after checkout don't carry org_id in metadata -- the router
    must resolve it via the customer id already persisted at checkout."""
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")
    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    container.auth().set_stripe_ids(org_id, "cus_123", "sub_123")
    fake_service.handle_webhook.return_value = {
        "event_type": "customer.subscription.updated",
        "stripe_customer_id": "cus_123",
        "subscription_status": "active",
    }

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 200
    assert container.auth().get_subscription_status(org_id) == "active"


def test_webhook_customer_id_desconhecido_nao_aplica_nada_nem_quebra():
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    fake_service.handle_webhook.return_value = {
        "event_type": "invoice.payment_failed",
        "stripe_customer_id": "cus_never_linked",
        "subscription_status": "past_due",
    }

    response = client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    assert response.status_code == 200
    assert container.audit.get_events(event="subscription_payment_failed") == []


def test_webhook_subscription_updated_nao_altera_plano_quando_price_nao_mapeado():
    """No "plan" key at all in the result (StripeService's own choice
    when it can't map a price id) means the router must not touch the
    plan -- only whatever fields are actually present get applied."""
    fake_service = MagicMock()
    client, container = _client(stripe_service=fake_service)
    owner_token = _login(client, "owner@test.com")
    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]
    container.auth().set_stripe_ids(org_id, "cus_123", "sub_123")
    container.auth().set_organization_plan(org_id, "pro")
    fake_service.handle_webhook.return_value = {
        "event_type": "customer.subscription.updated",
        "stripe_customer_id": "cus_123",
        "subscription_status": "active",
    }

    client.post(
        "/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "sig_test"}
    )

    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert plan_response.json()["data"]["plan"] == "pro"
