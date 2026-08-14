"""Tests for StripeService (Sprint 268, extended in Sprint 269 to handle
`invoice.payment_failed`/`customer.subscription.updated`/`deleted` and a
persistent, injectable idempotency store).

Sprint 269 changed `handle_webhook()`'s return shape for
`checkout.session.completed`: it now also carries `event_type`
(dispatches which action the caller takes) and `stripe_customer_id`/
`stripe_subscription_id` (the caller's own explicit requirement — Stripe
IDs must be persisted on the organization). Every pre-Sprint-269
assertion here that checked the old, narrower `{"org_id", "plan"}` shape
is updated to the new one; nothing about *when* a result is returned
(duplicate/idempotency/missing-metadata handling) changed.
"""

from unittest.mock import MagicMock, patch

import pytest
import stripe

from app.platform.billing.processed_events_store import ProcessedStripeEventStore
from app.platform.billing.stripe_service import StripeService


def _service(price_ids=None, event_store=None):
    return StripeService(
        secret_key="sk_test_fake",
        webhook_secret="whsec_fake",
        price_ids=price_ids if price_ids is not None else {"pro": "price_pro_123"},
        success_url="http://localhost/success",
        cancel_url="http://localhost/cancel",
        event_store=event_store,
    )


def _fake_event(
    event_id: str,
    event_type: str,
    metadata: dict | None = None,
    customer: str | None = None,
    subscription: str | None = None,
    status: str | None = None,
    items: list | None = None,
) -> dict:
    data_object = {"metadata": metadata or {}}

    if customer is not None:
        data_object["customer"] = customer
    if subscription is not None:
        data_object["subscription"] = subscription
    if status is not None:
        data_object["status"] = status
    if items is not None:
        data_object["items"] = {"data": items}

    return {"id": event_id, "type": event_type, "data": {"object": data_object}}


def test_create_checkout_session_retorna_url():
    service = _service()
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/cs_test_123"

    with patch(
        "app.platform.billing.stripe_service.stripe.checkout.Session.create",
        return_value=fake_session,
    ) as mock_create:
        url = service.create_checkout_session("org1", "pro")

    assert url == "https://checkout.stripe.com/pay/cs_test_123"

    _, kwargs = mock_create.call_args
    assert kwargs["mode"] == "subscription"
    assert kwargs["line_items"] == [{"price": "price_pro_123", "quantity": 1}]
    assert kwargs["metadata"] == {"org_id": "org1", "plan": "pro"}
    assert kwargs["api_key"] == "sk_test_fake"
    assert kwargs["success_url"] == "http://localhost/success"
    assert kwargs["cancel_url"] == "http://localhost/cancel"


def test_create_checkout_session_nao_usa_api_key_global():
    service = _service()
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/cs_test_123"

    original_api_key = stripe.api_key

    with patch(
        "app.platform.billing.stripe_service.stripe.checkout.Session.create",
        return_value=fake_session,
    ):
        service.create_checkout_session("org1", "pro")

    assert stripe.api_key == original_api_key


def test_create_checkout_session_plano_sem_price_id_levanta_value_error():
    service = _service(price_ids={})

    with pytest.raises(ValueError):
        service.create_checkout_session("org1", "pro")


def test_create_checkout_session_plano_com_price_id_vazio_levanta_value_error():
    service = _service(price_ids={"pro": ""})

    with pytest.raises(ValueError):
        service.create_checkout_session("org1", "pro")


def test_create_checkout_session_passa_idempotency_key():
    """Sprint 279 — optional, default `None`, so the pre-existing
    /billing/upgrade caller (which never passes one) is unaffected."""
    service = _service()
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/pay/cs_test_123"

    with patch(
        "app.platform.billing.stripe_service.stripe.checkout.Session.create",
        return_value=fake_session,
    ) as mock_create:
        service.create_checkout_session("org1", "pro", idempotency_key="key-123")

    _, kwargs = mock_create.call_args
    assert kwargs["idempotency_key"] == "key-123"


# --- Sprint 279: modify_subscription / cancel_subscription ---------------


def test_modify_subscription_busca_item_e_atualiza_preco():
    service = _service(price_ids={"pro": "price_pro_123", "enterprise": "price_ent_456"})
    fake_subscription = {"items": {"data": [{"id": "si_abc"}]}}

    with patch(
        "app.platform.billing.stripe_service.stripe.Subscription.retrieve",
        return_value=fake_subscription,
    ) as mock_retrieve, patch(
        "app.platform.billing.stripe_service.stripe.Subscription.modify"
    ) as mock_modify:
        service.modify_subscription("sub_1", "enterprise", idempotency_key="key-1")

    mock_retrieve.assert_called_once_with("sub_1", api_key="sk_test_fake")

    args, kwargs = mock_modify.call_args
    assert args[0] == "sub_1"
    assert kwargs["items"] == [{"id": "si_abc", "price": "price_ent_456"}]
    assert kwargs["api_key"] == "sk_test_fake"
    assert kwargs["idempotency_key"] == "key-1"


def test_modify_subscription_plano_sem_price_id_levanta_value_error():
    service = _service(price_ids={})

    with pytest.raises(ValueError):
        service.modify_subscription("sub_1", "pro")


def test_cancel_subscription_chama_delete_com_api_key_e_idempotency_key():
    service = _service()

    with patch(
        "app.platform.billing.stripe_service.stripe.Subscription.delete"
    ) as mock_delete:
        service.cancel_subscription("sub_1", idempotency_key="key-2")

    mock_delete.assert_called_once_with(
        "sub_1", api_key="sk_test_fake", idempotency_key="key-2"
    )


def test_handle_webhook_valida_assinatura_e_retorna_dados():
    service = _service()
    event = _fake_event(
        "evt_1",
        "checkout.session.completed",
        {"org_id": "org1", "plan": "pro"},
        customer="cus_123",
        subscription="sub_123",
    )

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ) as mock_construct:
        result = service.handle_webhook(b'{"fake": "payload"}', "sig_header_value")

    assert result == {
        "event_type": "checkout.session.completed",
        "org_id": "org1",
        "plan": "pro",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
    }
    mock_construct.assert_called_once_with(
        b'{"fake": "payload"}', "sig_header_value", "whsec_fake"
    )


def test_handle_webhook_assinatura_invalida_propaga_erro():
    service = _service()

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event",
        side_effect=stripe.error.SignatureVerificationError("bad sig", "sig_header"),
    ):
        with pytest.raises(stripe.error.SignatureVerificationError):
            service.handle_webhook(b"payload", "bad-sig")


def test_handle_webhook_ignora_tipos_de_evento_nao_tratados():
    """Sprint 269 now handles customer.subscription.deleted (see
    test_handle_webhook_subscription_deleted_* below) — this test uses a
    genuinely unhandled type instead, to keep testing "unknown event type
    -> None" rather than accidentally re-testing a now-handled one."""
    service = _service()
    event = _fake_event("evt_2", "customer.created")

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result is None


def test_handle_webhook_e_idempotente():
    service = _service()
    event = _fake_event("evt_3", "checkout.session.completed", {"org_id": "org1", "plan": "pro"})

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        first = service.handle_webhook(b"payload", "sig")
        second = service.handle_webhook(b"payload", "sig")

    assert first == {
        "event_type": "checkout.session.completed",
        "org_id": "org1",
        "plan": "pro",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
    }
    assert second is None


def test_handle_webhook_eventos_diferentes_nao_sao_deduplicados():
    service = _service()
    event_a = _fake_event("evt_a", "checkout.session.completed", {"org_id": "org1", "plan": "pro"})
    event_b = _fake_event("evt_b", "checkout.session.completed", {"org_id": "org2", "plan": "pro"})

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event",
        side_effect=[event_a, event_b],
    ):
        first = service.handle_webhook(b"payload_a", "sig")
        second = service.handle_webhook(b"payload_b", "sig")

    assert first["org_id"] == "org1"
    assert second["org_id"] == "org2"


def test_handle_webhook_sem_metadata_retorna_none():
    service = _service()
    event = _fake_event("evt_4", "checkout.session.completed", metadata={})

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result is None


# --- Sprint 269: invoice.payment_failed ---------------------------------


def test_handle_webhook_payment_failed_retorna_status_past_due():
    service = _service()
    event = _fake_event("evt_pf1", "invoice.payment_failed", customer="cus_123")

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result == {
        "event_type": "invoice.payment_failed",
        "stripe_customer_id": "cus_123",
        "subscription_status": "past_due",
    }
    # Deliberately no "plan" key: a single failed payment shouldn't
    # revoke paid-plan access during Stripe's own retry window.
    assert "plan" not in result


def test_handle_webhook_payment_failed_sem_customer_retorna_none():
    service = _service()
    event = _fake_event("evt_pf2", "invoice.payment_failed")

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result is None


# --- Sprint 269: customer.subscription.deleted --------------------------


def test_handle_webhook_subscription_deleted_retorna_canceled_e_plano_free():
    service = _service()
    event = _fake_event("evt_sd1", "customer.subscription.deleted", customer="cus_123")

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result == {
        "event_type": "customer.subscription.deleted",
        "stripe_customer_id": "cus_123",
        "subscription_status": "canceled",
        "plan": "free",
    }


def test_handle_webhook_subscription_deleted_sem_customer_retorna_none():
    service = _service()
    event = _fake_event("evt_sd2", "customer.subscription.deleted")

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result is None


# --- Sprint 269: customer.subscription.updated ---------------------------


def test_handle_webhook_subscription_updated_normaliza_status_ativo():
    service = _service()
    event = _fake_event(
        "evt_su1", "customer.subscription.updated", customer="cus_123", status="trialing"
    )

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result["subscription_status"] == "active"


def test_handle_webhook_subscription_updated_normaliza_status_past_due():
    service = _service()
    event = _fake_event(
        "evt_su2", "customer.subscription.updated", customer="cus_123", status="unpaid"
    )

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result["subscription_status"] == "past_due"


def test_handle_webhook_subscription_updated_status_desconhecido_passa_adiante():
    """A Stripe status this code hasn't explicitly mapped is recorded as-
    is, not silently dropped."""
    service = _service()
    event = _fake_event(
        "evt_su3", "customer.subscription.updated", customer="cus_123", status="paused"
    )

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result["subscription_status"] == "paused"


def test_handle_webhook_subscription_updated_resolve_plano_pelo_price_id():
    service = _service(price_ids={"pro": "price_pro_123", "enterprise": "price_ent_456"})
    event = _fake_event(
        "evt_su4",
        "customer.subscription.updated",
        customer="cus_123",
        status="active",
        items=[{"price": {"id": "price_ent_456"}}],
    )

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result["plan"] == "enterprise"


def test_handle_webhook_subscription_updated_price_id_desconhecido_omite_plano():
    service = _service(price_ids={"pro": "price_pro_123"})
    event = _fake_event(
        "evt_su5",
        "customer.subscription.updated",
        customer="cus_123",
        status="active",
        items=[{"price": {"id": "price_not_mapped"}}],
    )

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert "plan" not in result


def test_handle_webhook_subscription_updated_sem_customer_retorna_none():
    service = _service()
    event = _fake_event("evt_su6", "customer.subscription.updated", status="active")

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        result = service.handle_webhook(b"payload", "sig")

    assert result is None


# --- Sprint 269: persistent (injectable) idempotency store ---------------


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, str] = {}

    def get(self, key):
        return self._values.get(key)

    def set(self, key, value, ex=None):
        self._values[key] = value
        return True


def test_handle_webhook_usa_event_store_quando_fornecido():
    fake_redis = _FakeRedisClient()
    event_store = ProcessedStripeEventStore(fake_redis)
    service = _service(event_store=event_store)
    event = _fake_event("evt_es1", "checkout.session.completed", {"org_id": "org1", "plan": "pro"})

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        first = service.handle_webhook(b"payload", "sig")
        second = service.handle_webhook(b"payload", "sig")

    assert first is not None
    assert second is None
    assert event_store.has_processed("evt_es1") is True


def test_handle_webhook_event_store_e_independente_da_instancia():
    """The whole point of a persistent, shared store over the in-memory
    set: a *second* StripeService instance (simulating a different
    worker process) sees the same "already processed" state."""
    fake_redis = _FakeRedisClient()
    event_store_a = ProcessedStripeEventStore(fake_redis)
    event_store_b = ProcessedStripeEventStore(fake_redis)
    service_a = _service(event_store=event_store_a)
    service_b = _service(event_store=event_store_b)
    event = _fake_event("evt_es2", "checkout.session.completed", {"org_id": "org1", "plan": "pro"})

    with patch(
        "app.platform.billing.stripe_service.stripe.Webhook.construct_event", return_value=event
    ):
        first = service_a.handle_webhook(b"payload", "sig")
        second = service_b.handle_webhook(b"payload", "sig")

    assert first is not None
    assert second is None
