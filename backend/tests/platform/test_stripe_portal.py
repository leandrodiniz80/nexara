"""Tests for StripeSyncService.create_portal_session() and
StripeService.create_customer_portal_session() (Sprint 280).
"""

from unittest.mock import MagicMock, patch

from app.platform.billing.stripe_service import StripeService
from app.platform.billing.stripe_sync import StripeSyncService


class FakeAuth:
    def __init__(self, stripe_ids: dict | None = None):
        self._stripe_ids = stripe_ids or {}

    def get_stripe_ids(self, org_id: str) -> dict:
        return self._stripe_ids


def _service():
    return StripeService(
        secret_key="sk_test_fake",
        webhook_secret="whsec_fake",
        price_ids={"pro": "price_pro_123"},
    )


# --- StripeSyncService.create_portal_session() ----------------------------


def test_cria_sessao_corretamente():
    stripe_service = MagicMock()
    stripe_service.create_customer_portal_session.return_value = (
        "https://billing.stripe.com/session/xyz"
    )
    auth = FakeAuth(stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"})
    sync = StripeSyncService(stripe_service, auth)

    result = sync.create_portal_session("org_1", "https://app.example.com/billing")

    assert result == {"status": "portal_created", "url": "https://billing.stripe.com/session/xyz"}


def test_retorna_no_customer_se_nao_houver_customer_id():
    stripe_service = MagicMock()
    auth = FakeAuth(stripe_ids={})
    sync = StripeSyncService(stripe_service, auth)

    result = sync.create_portal_session("org_1", "https://app.example.com/billing")

    assert result == {"status": "no_customer", "reason": "no_stripe_customer"}
    stripe_service.create_customer_portal_session.assert_not_called()


def test_passa_return_url_corretamente():
    stripe_service = MagicMock()
    stripe_service.create_customer_portal_session.return_value = "https://billing.stripe.com/x"
    auth = FakeAuth(stripe_ids={"stripe_customer_id": "cus_1"})
    sync = StripeSyncService(stripe_service, auth)

    sync.create_portal_session("org_1", "https://app.example.com/billing")

    _, kwargs = stripe_service.create_customer_portal_session.call_args
    assert kwargs["customer_id"] == "cus_1"
    assert kwargs["return_url"] == "https://app.example.com/billing"


def test_cada_chamada_gera_uma_idempotency_key_diferente():
    """Regression guard for the spec's own bug: a static per-org key
    would make Stripe return the same cached (possibly already-consumed)
    session to a customer who opens "Manage Billing" more than once."""
    stripe_service = MagicMock()
    stripe_service.create_customer_portal_session.return_value = "https://billing.stripe.com/x"
    auth = FakeAuth(stripe_ids={"stripe_customer_id": "cus_1"})
    sync = StripeSyncService(stripe_service, auth)

    sync.create_portal_session("org_1", "https://app.example.com/billing")
    sync.create_portal_session("org_1", "https://app.example.com/billing")

    calls = stripe_service.create_customer_portal_session.call_args_list
    key_1 = calls[0].kwargs["idempotency_key"]
    key_2 = calls[1].kwargs["idempotency_key"]
    assert key_1 != key_2
    assert stripe_service.create_customer_portal_session.call_count == 2


def test_portal_session_nao_muta_plano_interno():
    """FakeAuth here has no set_organization_plan()/set_subscription_
    status() at all -- any attempt to call either would raise
    AttributeError and fail this test."""
    stripe_service = MagicMock()
    stripe_service.create_customer_portal_session.return_value = "https://billing.stripe.com/x"
    auth = FakeAuth(stripe_ids={"stripe_customer_id": "cus_1"})
    sync = StripeSyncService(stripe_service, auth)

    sync.create_portal_session("org_1", "https://app.example.com/billing")


# --- StripeService.create_customer_portal_session() ------------------------


def test_service_cria_sessao_e_retorna_url():
    service = _service()
    fake_session = MagicMock()
    fake_session.url = "https://billing.stripe.com/session/abc"

    with patch(
        "app.platform.billing.stripe_service.stripe.billing_portal.Session.create",
        return_value=fake_session,
    ) as mock_create:
        url = service.create_customer_portal_session("cus_1", "https://app.example.com/billing")

    assert url == "https://billing.stripe.com/session/abc"
    _, kwargs = mock_create.call_args
    assert kwargs["customer"] == "cus_1"
    assert kwargs["return_url"] == "https://app.example.com/billing"


def test_service_passa_api_key_explicitamente():
    """Regression guard: the spec's own version omitted api_key entirely
    -- every other method in this class passes it explicitly rather than
    relying on the stripe module's global state."""
    service = _service()
    fake_session = MagicMock()
    fake_session.url = "https://billing.stripe.com/session/abc"

    with patch(
        "app.platform.billing.stripe_service.stripe.billing_portal.Session.create",
        return_value=fake_session,
    ) as mock_create:
        service.create_customer_portal_session("cus_1", "https://app.example.com/billing")

    _, kwargs = mock_create.call_args
    assert kwargs["api_key"] == "sk_test_fake"


def test_service_passa_idempotency_key():
    service = _service()
    fake_session = MagicMock()
    fake_session.url = "https://billing.stripe.com/session/abc"

    with patch(
        "app.platform.billing.stripe_service.stripe.billing_portal.Session.create",
        return_value=fake_session,
    ) as mock_create:
        service.create_customer_portal_session(
            "cus_1", "https://app.example.com/billing", idempotency_key="key-1"
        )

    _, kwargs = mock_create.call_args
    assert kwargs["idempotency_key"] == "key-1"
