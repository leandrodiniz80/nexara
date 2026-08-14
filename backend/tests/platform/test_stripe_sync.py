"""Tests for StripeSyncService (Sprint 279).

`stripe_service` here is a MagicMock, not a real StripeService/Stripe
SDK call — StripeSyncService only ever calls through it (create_checkout
_session/modify_subscription/cancel_subscription), never the `stripe`
module directly, so mocking at that boundary is enough; the SDK-call
level itself is already covered by test_stripe_service.py.
"""

from unittest.mock import MagicMock

from app.platform.billing.stripe_sync import StripeSyncService


class FakeAuth:
    def __init__(self, stripe_ids: dict | None = None, subscription_status: str | None = None):
        self._stripe_ids = stripe_ids or {}
        self._subscription_status = subscription_status

    def get_stripe_ids(self, org_id: str) -> dict:
        return self._stripe_ids

    def get_subscription_status(self, org_id: str) -> str | None:
        return self._subscription_status


class FakeActionStore:
    def __init__(self):
        self._processed: set[str] = set()

    def has_processed(self, action_id: str) -> bool:
        return action_id in self._processed

    def mark_processed(self, action_id: str) -> None:
        self._processed.add(action_id)


def test_upgrade_cria_checkout_quando_nao_tem_subscription():
    stripe_service = MagicMock()
    stripe_service.create_checkout_session.return_value = "https://checkout.stripe.com/cs_1"
    auth = FakeAuth(stripe_ids={})
    sync = StripeSyncService(stripe_service, auth)

    result = sync.upgrade_subscription("org_1", "pro")

    assert result == {"status": "pending", "checkout_url": "https://checkout.stripe.com/cs_1"}
    stripe_service.create_checkout_session.assert_called_once()
    stripe_service.modify_subscription.assert_not_called()


def test_upgrade_cria_checkout_quando_subscription_esta_cancelada():
    """A stale stripe_subscription_id from a past churn (the existing
    subscription.deleted webhook handler never clears it) must not be
    treated as "active enough to modify" -- Subscription.modify() on an
    already-canceled subscription would fail."""
    stripe_service = MagicMock()
    stripe_service.create_checkout_session.return_value = "https://checkout.stripe.com/cs_2"
    auth = FakeAuth(
        stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"},
        subscription_status="canceled",
    )
    sync = StripeSyncService(stripe_service, auth)

    result = sync.upgrade_subscription("org_1", "pro")

    assert result["status"] == "pending"
    stripe_service.modify_subscription.assert_not_called()


def test_upgrade_modifica_subscription_quando_ja_existe_e_ativa():
    stripe_service = MagicMock()
    auth = FakeAuth(
        stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"},
        subscription_status="active",
    )
    sync = StripeSyncService(stripe_service, auth)

    result = sync.upgrade_subscription("org_1", "enterprise")

    assert result == {"status": "applied"}
    stripe_service.modify_subscription.assert_called_once()
    args, kwargs = stripe_service.modify_subscription.call_args
    assert args[0] == "sub_1"
    assert args[1] == "enterprise"
    stripe_service.create_checkout_session.assert_not_called()


def test_upgrade_trialing_conta_como_subscription_ativa():
    stripe_service = MagicMock()
    auth = FakeAuth(
        stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"},
        subscription_status="trialing",
    )
    sync = StripeSyncService(stripe_service, auth)

    result = sync.upgrade_subscription("org_1", "pro")

    assert result == {"status": "applied"}
    stripe_service.modify_subscription.assert_called_once()


def test_upgrade_le_stripe_ids_por_chave_nao_por_desempacotamento():
    """Regression guard: get_stripe_ids() returns a dict
    ({"stripe_customer_id": ..., "stripe_subscription_id": ...}), not a
    2-tuple. Unpacking it as `a, b = get_stripe_ids(...)` would silently
    bind the two *key strings* to a/b, never the actual ids -- this test
    fails loudly (KeyError-shaped wrong behavior) if that regression is
    ever reintroduced, since a real subscription id ("sub_1") wouldn't
    match either literal key string."""
    stripe_service = MagicMock()
    auth = FakeAuth(
        stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"},
        subscription_status="active",
    )
    sync = StripeSyncService(stripe_service, auth)

    sync.upgrade_subscription("org_1", "pro")

    args, _ = stripe_service.modify_subscription.call_args
    assert args[0] == "sub_1"


def test_downgrade_cancela_subscription():
    stripe_service = MagicMock()
    auth = FakeAuth(stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"})
    sync = StripeSyncService(stripe_service, auth)

    result = sync.downgrade_subscription("org_1")

    assert result == {"status": "applied"}
    stripe_service.cancel_subscription.assert_called_once()
    args, _ = stripe_service.cancel_subscription.call_args
    assert args[0] == "sub_1"


def test_downgrade_sem_subscription_e_ignorado():
    stripe_service = MagicMock()
    auth = FakeAuth(stripe_ids={})
    sync = StripeSyncService(stripe_service, auth)

    result = sync.downgrade_subscription("org_1")

    assert result == {"status": "skipped", "reason": "no_subscription"}
    stripe_service.cancel_subscription.assert_not_called()


def test_idempotency_key_e_passado_para_o_stripe_service():
    stripe_service = MagicMock()
    stripe_service.create_checkout_session.return_value = "https://checkout.stripe.com/cs_1"
    auth = FakeAuth(stripe_ids={})
    sync = StripeSyncService(stripe_service, auth)

    sync.upgrade_subscription("org_1", "pro")

    _, kwargs = stripe_service.create_checkout_session.call_args
    assert kwargs["idempotency_key"] == "decision_engine:upgrade:org_1:pro"


def test_action_store_bloqueia_execucao_duplicada():
    stripe_service = MagicMock()
    stripe_service.create_checkout_session.return_value = "https://checkout.stripe.com/cs_1"
    auth = FakeAuth(stripe_ids={})
    action_store = FakeActionStore()
    sync = StripeSyncService(stripe_service, auth, action_store=action_store)

    first = sync.upgrade_subscription("org_1", "pro")
    second = sync.upgrade_subscription("org_1", "pro")

    assert first["status"] == "pending"
    assert second == {"status": "skipped", "reason": "already_processed"}
    stripe_service.create_checkout_session.assert_called_once()


def test_action_store_nao_bloqueia_planos_diferentes():
    stripe_service = MagicMock()
    stripe_service.create_checkout_session.return_value = "https://checkout.stripe.com/cs_1"
    auth = FakeAuth(stripe_ids={})
    action_store = FakeActionStore()
    sync = StripeSyncService(stripe_service, auth, action_store=action_store)

    sync.upgrade_subscription("org_1", "pro")
    second = sync.upgrade_subscription("org_1", "enterprise")

    assert second["status"] == "pending"
    assert stripe_service.create_checkout_session.call_count == 2


def test_sem_action_store_nao_bloqueia_nada():
    stripe_service = MagicMock()
    stripe_service.create_checkout_session.return_value = "https://checkout.stripe.com/cs_1"
    auth = FakeAuth(stripe_ids={})
    sync = StripeSyncService(stripe_service, auth, action_store=None)

    sync.upgrade_subscription("org_1", "pro")
    second = sync.upgrade_subscription("org_1", "pro")

    assert second["status"] == "pending"
    assert stripe_service.create_checkout_session.call_count == 2


def test_downgrade_nunca_muda_plano_interno():
    """StripeSyncService's own hard rule: it only ever talks to Stripe,
    never touches PlatformAuth's plan/subscription_status fields --
    FakeAuth here has no set_organization_plan()/set_subscription_status()
    method at all, so any attempt to call either would raise
    AttributeError and fail this test."""
    stripe_service = MagicMock()
    auth = FakeAuth(stripe_ids={"stripe_customer_id": "cus_1", "stripe_subscription_id": "sub_1"})
    sync = StripeSyncService(stripe_service, auth)

    sync.downgrade_subscription("org_1")
