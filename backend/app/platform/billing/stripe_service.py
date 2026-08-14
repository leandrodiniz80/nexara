import stripe

_CHECKOUT_COMPLETED = "checkout.session.completed"
_PAYMENT_FAILED = "invoice.payment_failed"
_SUBSCRIPTION_DELETED = "customer.subscription.deleted"
_SUBSCRIPTION_UPDATED = "customer.subscription.updated"

# Stripe subscription statuses collapsed to this platform's own smaller
# vocabulary (matching the two other event handlers below) — a status
# this map doesn't recognize is passed through unchanged rather than
# dropped, so a Stripe status this code hasn't been taught about yet is
# still recorded (just not normalized) instead of silently lost.
_SUBSCRIPTION_STATUS_MAP = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
}


def _first_item_price_id(subscription_data: dict) -> str | None:
    items = (subscription_data.get("items") or {}).get("data") or []

    if not items:
        return None

    return (items[0].get("price") or {}).get("id")


class StripeService:
    """Talks to Stripe for plan checkout + webhook verification (Sprint
    268/269). The API key is passed explicitly on every call (never
    assigned to the `stripe` module's global `api_key`) so that multiple
    instances — e.g. a real one and a test double — never interfere with
    each other's credentials.

    Deliberately has no `PlatformAuth` dependency of its own — org/plan
    data is a concern for whoever calls `handle_webhook()` (the
    `/billing/webhook` route), not this class. Events after checkout
    (`invoice.payment_failed`, `customer.subscription.updated`/
    `deleted`) don't reliably carry the original checkout metadata
    (`org_id`/`plan` — Stripe doesn't guarantee it propagates from a
    Checkout Session onto every later event for the resulting
    subscription), only a `customer` id — so the result for those event
    types carries `stripe_customer_id` for the *caller* to resolve
    (`PlatformAuth.find_organization_by_stripe_customer()`), rather than
    this class reaching for `PlatformAuth` itself.
    """

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str,
        price_ids: dict[str, str] | None = None,
        success_url: str = "http://localhost:3000/billing/success",
        cancel_url: str = "http://localhost:3000/billing/cancel",
        event_store=None,
    ):
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._price_ids = price_ids or {}
        self._success_url = success_url
        self._cancel_url = cancel_url
        self._processed_event_ids: set[str] = set()
        # Optional persistent idempotency store (Sprint 269) — see
        # processed_events_store.py. `None` keeps the original Sprint
        # 268 in-memory-set behavior, unchanged.
        self._event_store = event_store

    def _is_duplicate(self, event_id: str) -> bool:
        if self._event_store is not None:
            return self._event_store.has_processed(event_id)

        return event_id in self._processed_event_ids

    def _mark_processed(self, event_id: str) -> None:
        if self._event_store is not None:
            self._event_store.mark_processed(event_id)
        else:
            self._processed_event_ids.add(event_id)

    def _plan_for_price_id(self, price_id: str | None) -> str | None:
        if price_id is None:
            return None

        for plan, mapped_price_id in self._price_ids.items():
            if mapped_price_id == price_id:
                return plan

        return None

    def create_checkout_session(
        self, org_id: str, plan: str, idempotency_key: str | None = None
    ) -> str:
        """`idempotency_key` (Sprint 279, optional, defaults to `None` —
        unchanged behavior for the pre-existing `/billing/upgrade` caller,
        which never passes one) is Stripe's own mechanism for making a
        retried request provably a no-op rather than a duplicate side
        effect, passed straight through to the Stripe SDK/API. Used by
        `StripeSyncService` so a retried `upgrade_subscription()` call
        can't create two checkout sessions for the same intended action.
        """
        price_id = self._price_ids.get(plan)

        if not price_id:
            raise ValueError(f"No Stripe price configured for plan '{plan}'")

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=self._success_url,
            cancel_url=self._cancel_url,
            metadata={"org_id": org_id, "plan": plan},
            api_key=self._secret_key,
            idempotency_key=idempotency_key,
        )

        return session.url

    def modify_subscription(
        self, subscription_id: str, plan: str, idempotency_key: str | None = None
    ) -> None:
        """Sprint 279. Changes an *existing, active* subscription's price
        to `plan`'s configured price — used when an organization already
        has a real Stripe subscription (as opposed to `create_checkout_
        session()`, for an organization with none). Retrieves the
        subscription first to find its subscription-item id: Stripe's
        `Subscription.modify()` needs `items=[{"id": <item_id>, "price":
        <new_price_id>}]`, not just a bare subscription id, and nothing
        in this codebase persists the item id anywhere. Never changes
        `PlatformAuth`'s own `plan` field — the caller (`StripeSyncService`)
        deliberately waits for the `customer.subscription.updated`
        webhook to do that, keeping Stripe as the single source of truth
        for what plan a paying customer is actually on.
        """
        price_id = self._price_ids.get(plan)

        if not price_id:
            raise ValueError(f"No Stripe price configured for plan '{plan}'")

        subscription = stripe.Subscription.retrieve(subscription_id, api_key=self._secret_key)
        item_id = subscription["items"]["data"][0]["id"]

        stripe.Subscription.modify(
            subscription_id,
            items=[{"id": item_id, "price": price_id}],
            proration_behavior="create_prorations",
            api_key=self._secret_key,
            idempotency_key=idempotency_key,
        )

    def cancel_subscription(
        self, subscription_id: str, idempotency_key: str | None = None
    ) -> None:
        """Sprint 279. Cancels a real Stripe subscription outright — used
        by `StripeSyncService.downgrade_subscription()`. Never changes
        `PlatformAuth`'s own `plan`/`subscription_status` fields; the
        caller waits for the `customer.subscription.deleted` webhook to
        do that (this codebase's existing handler already sets
        `plan="free"`/`subscription_status="canceled"` when it fires —
        see `_handle_subscription_deleted()` above).
        """
        stripe.Subscription.delete(
            subscription_id, api_key=self._secret_key, idempotency_key=idempotency_key
        )

    def create_customer_portal_session(
        self, customer_id: str, return_url: str, idempotency_key: str | None = None
    ) -> str:
        """Sprint 280. Real fix over the spec's own version: it omitted
        `api_key=self._secret_key` entirely — the one thing every other
        method in this class does unconditionally (see this class's own
        docstring and `test_create_checkout_session_nao_usa_api_key_
        global`). Without it, the call would either fail outright (no
        key configured on the `stripe` module globally) or, worse,
        silently use whatever `stripe.api_key` happens to be set
        globally at that moment — exactly the cross-instance credential
        mixup this class was built from the start to avoid.
        """
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
            api_key=self._secret_key,
            idempotency_key=idempotency_key,
        )

        return session.url

    def handle_webhook(self, payload: bytes, sig_header: str) -> dict | None:
        """Signature verified first, unconditionally, before any event
        data is trusted or even inspected — unchanged from Sprint 268,
        and applies uniformly to every event type this handles, not just
        `checkout.session.completed`.

        Returns `None` for a duplicate delivery, an event type this
        doesn't handle, or one whose payload is missing data this can't
        safely act on (e.g. no `customer` id at all) — the caller (the
        `/billing/webhook` route) must still acknowledge Stripe with a
        2xx in every one of those cases; only a genuine processing
        failure should make Stripe retry.
        """
        event = stripe.Webhook.construct_event(payload, sig_header, self._webhook_secret)

        event_id = event["id"]

        if self._is_duplicate(event_id):
            return None

        self._mark_processed(event_id)

        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == _CHECKOUT_COMPLETED:
            return self._handle_checkout_completed(event_type, data)

        if event_type == _PAYMENT_FAILED:
            return self._handle_payment_failed(event_type, data)

        if event_type == _SUBSCRIPTION_DELETED:
            return self._handle_subscription_deleted(event_type, data)

        if event_type == _SUBSCRIPTION_UPDATED:
            return self._handle_subscription_updated(event_type, data)

        return None

    @staticmethod
    def _handle_checkout_completed(event_type: str, data: dict) -> dict | None:
        metadata = data.get("metadata") or {}
        org_id = metadata.get("org_id")
        plan = metadata.get("plan")

        if not org_id or not plan:
            return None

        return {
            "event_type": event_type,
            "org_id": org_id,
            "plan": plan,
            "stripe_customer_id": data.get("customer"),
            "stripe_subscription_id": data.get("subscription"),
        }

    @staticmethod
    def _handle_payment_failed(event_type: str, data: dict) -> dict | None:
        customer_id = data.get("customer")

        if not customer_id:
            return None

        # Deliberately does not change `plan`: Stripe retries a failed
        # payment over its own dunning window before actually canceling
        # the subscription (`customer.subscription.deleted`, handled
        # separately) — losing paid-plan access on the very first missed
        # charge would be needlessly aggressive.
        return {
            "event_type": event_type,
            "stripe_customer_id": customer_id,
            "subscription_status": "past_due",
        }

    @staticmethod
    def _handle_subscription_deleted(event_type: str, data: dict) -> dict | None:
        customer_id = data.get("customer")

        if not customer_id:
            return None

        return {
            "event_type": event_type,
            "stripe_customer_id": customer_id,
            "subscription_status": "canceled",
            "plan": "free",
        }

    def _handle_subscription_updated(self, event_type: str, data: dict) -> dict | None:
        customer_id = data.get("customer")

        if not customer_id:
            return None

        result = {
            "event_type": event_type,
            "stripe_customer_id": customer_id,
            "subscription_status": _SUBSCRIPTION_STATUS_MAP.get(
                data.get("status"), data.get("status")
            ),
        }

        plan = self._plan_for_price_id(_first_item_price_id(data))
        if plan is not None:
            result["plan"] = plan

        return result
