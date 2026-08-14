import uuid


class StripeSyncService:
    """Routes real plan changes through Stripe (Sprint 279) — the
    counterpart to `BillingDecisionEngine`'s previous, Stripe-unaware
    execution (Sprint 278): "Stripe é a fonte da verdade para billing",
    per the user's own explicit architectural decision for this sprint.

    Neither `upgrade_subscription()` nor `downgrade_subscription()` ever
    touches `PlatformAuth`'s own `plan`/`subscription_status` fields —
    that stays the exclusive job of the existing Stripe webhook handler
    in `billing.py` (`checkout.session.completed` /
    `customer.subscription.updated` / `customer.subscription.deleted`),
    which is already the single place those fields get written from
    Stripe. This class only ever *initiates* a Stripe-side change and
    reports what it did; it never predicts or assumes the outcome.

    `action_store` (optional, `(id) -> bool` `has_processed`/
    `mark_processed` shape — see `ProcessedStripeEventStore`, Sprint
    269) guards against the same logical action (same org, same action
    type, same target plan) being submitted to Stripe twice in quick
    succession — a double-click, a client retry after a slow response —
    on top of the idempotency key passed to Stripe itself on every
    mutating call (protects against duplicate provider-side effects,
    e.g. two proration invoices, from a network-level retry of the exact
    same request). Two different, complementary protections for two
    different failure modes; `None` (no store configured) disables the
    app-level guard only, not the Stripe-level one — Stripe's idempotency
    key is generated fresh per call either way.
    """

    def __init__(self, stripe_service, auth, action_store=None):
        self.stripe = stripe_service
        self.auth = auth
        self._action_store = action_store

    def _action_id(self, org_id: str, action: str, target_plan: str) -> str:
        return f"decision_engine:{action}:{org_id}:{target_plan}"

    def _already_processed(self, action_id: str) -> bool:
        if self._action_store is None:
            return False

        return self._action_store.has_processed(action_id)

    def _mark_processed(self, action_id: str) -> None:
        if self._action_store is not None:
            self._action_store.mark_processed(action_id)

    def upgrade_subscription(self, org_id: str, target_plan: str) -> dict:
        """Never applies `target_plan` internally — see this class's own
        docstring. Returns one of:

        - `{"status": "pending", "checkout_url": ...}` — no active Stripe
          subscription exists for this organization (either none at
          all, or its last known one is already `canceled`), so a new
          Checkout Session was created; nothing changes until the
          *customer* completes it. Per the user's own explicit decision
          for this sprint: the caller (`BillingDecisionEngine`) must
          report this as pending, never as an applied upgrade.
        - `{"status": "applied"}` — an active subscription already
          exists; its price was changed via `Subscription.modify()`.
          The organization's actual plan still only updates once the
          resulting `customer.subscription.updated` webhook arrives —
          "applied" here means "the change was successfully submitted
          to Stripe", not "the org is confirmed to be on the new plan".
        - `{"status": "skipped", "reason": "already_processed"}` — the
          exact same (org, "upgrade", target_plan) action was already
          submitted within the action-idempotency window; not
          resubmitted.

        The spec's own version of this method read `auth.get_stripe_ids
        (org_id)` and unpacked it as `customer_id, subscription_id =
        auth.get_stripe_ids(org_id)` — but that method returns a `dict`
        (`{"stripe_customer_id": ..., "stripe_subscription_id": ...}`),
        not a 2-tuple; unpacking a 2-key dict that way silently binds
        the two *key strings* ("stripe_customer_id", "stripe_
        subscription_id") to `customer_id`/`subscription_id`, never the
        actual ids. Reads both fields by key instead.

        Also checks `subscription_status`, not just whether a
        `stripe_subscription_id` is on file: an organization that
        churned via Stripe and reverted to the free plan (the existing
        `customer.subscription.deleted` handler sets `plan="free"` but
        never clears the now-stale `stripe_subscription_id`/`stripe_
        customer_id` fields) still has an id on record, but that
        subscription is `canceled` and permanently terminal on Stripe's
        side — `Subscription.modify()` on it would fail. Only a
        subscription id whose last known status isn't `canceled` is
        treated as "active enough to modify"; anything else creates a
        fresh Checkout Session instead.
        """
        action_id = self._action_id(org_id, "upgrade", target_plan)

        if self._already_processed(action_id):
            return {"status": "skipped", "reason": "already_processed"}

        stripe_ids = self.auth.get_stripe_ids(org_id)
        subscription_id = stripe_ids.get("stripe_subscription_id")
        status = self.auth.get_subscription_status(org_id)
        has_active_subscription = subscription_id is not None and status != "canceled"

        if not has_active_subscription:
            checkout_url = self.stripe.create_checkout_session(
                org_id, target_plan, idempotency_key=action_id
            )
            self._mark_processed(action_id)

            return {"status": "pending", "checkout_url": checkout_url}

        self.stripe.modify_subscription(subscription_id, target_plan, idempotency_key=action_id)
        self._mark_processed(action_id)

        return {"status": "applied"}

    def downgrade_subscription(self, org_id: str) -> dict:
        """Never applies the plan change internally — see this class's
        own docstring; the existing `customer.subscription.deleted`
        webhook handler already sets `plan="free"`/`subscription_status=
        "canceled"` once Stripe confirms the cancellation.

        Returns `{"status": "applied"}` once `Subscription.delete()` is
        submitted (cancellation is a direct, synchronous Stripe API call
        with no customer action required, unlike upgrade's checkout
        flow — there is no "pending" state to report here), `{"status":
        "skipped", "reason": "no_subscription"}` if the organization has
        no `stripe_subscription_id` on file at all (nothing to cancel —
        the caller should fall back to a direct internal plan change
        instead, see `BillingDecisionEngine._apply_plan_change()`), or
        the `"already_processed"` skip, same as `upgrade_subscription()`.
        """
        action_id = self._action_id(org_id, "downgrade", "free")

        if self._already_processed(action_id):
            return {"status": "skipped", "reason": "already_processed"}

        stripe_ids = self.auth.get_stripe_ids(org_id)
        subscription_id = stripe_ids.get("stripe_subscription_id")

        if subscription_id is None:
            return {"status": "skipped", "reason": "no_subscription"}

        self.stripe.cancel_subscription(subscription_id, idempotency_key=action_id)
        self._mark_processed(action_id)

        return {"status": "applied"}

    def create_portal_session(self, org_id: str, return_url: str) -> dict:
        """Sprint 280 — self-serve Stripe Customer Portal: the customer
        manages their own upgrade/downgrade/cancellation/payment method
        directly through Stripe's own hosted UI from here on, never
        through `PlatformAuth`/`plan` mutation on this end. Same hard
        rule as `upgrade_subscription()`/`downgrade_subscription()`:
        never touches `plan`/`subscription_status` — those still only
        ever change via the existing `customer.subscription.updated`/
        `deleted` webhook, once Stripe confirms whatever the customer
        actually did in the portal.

        Returns `{"status": "no_customer", "reason": "no_stripe_
        customer"}` if the organization has never had a Stripe checkout
        completed (nothing to manage yet — the caller should point them
        at the regular upgrade flow instead), or `{"status": "portal_
        created", "url": ...}`.

        Deliberately does *not* use `_action_id()`/`_already_processed()`
        the way the two mutating methods above do: those exist to guard
        `BillingDecisionEngine`'s *automated* re-invocation of the same
        logical action, but a portal session is always an explicit,
        live, non-mutating request from an authenticated user — the
        spec's own version reused a single static `f"portal_{org_id}"`
        idempotency key for every call, which would make Stripe return
        the *same cached session* (Stripe caches idempotent responses
        for 24h) to a customer who legitimately opens "Manage Billing"
        more than once in a day, quite possibly a session URL they
        already consumed. A fresh key per call means every request gets
        its own live session, as it should.
        """
        stripe_ids = self.auth.get_stripe_ids(org_id)
        customer_id = stripe_ids.get("stripe_customer_id")

        if not customer_id:
            return {"status": "no_customer", "reason": "no_stripe_customer"}

        url = self.stripe.create_customer_portal_session(
            customer_id=customer_id,
            return_url=return_url,
            idempotency_key=f"portal_{org_id}_{uuid.uuid4().hex}",
        )

        return {"status": "portal_created", "url": url}
