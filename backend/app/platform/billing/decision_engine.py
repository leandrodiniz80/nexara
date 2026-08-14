import time

_SECONDS_PER_DAY = 86400
_MIN_TENURE_DAYS_FOR_DOWNGRADE = 30
_DOWNGRADE_HEALTH_THRESHOLD = 40
_DOWNGRADE_USAGE_RATIO_THRESHOLD = 0.1
_UPGRADE_HEALTH_THRESHOLD = 85


class BillingDecisionEngine:
    """Rule-based auto-upgrade / auto-retention / downgrade-recommendation
    engine (Sprint 278, Stripe-routed execution added Sprint 279,
    downgrade execution removed and notifications added Sprint 281).

    Per the user's own explicit product decision for Sprint 278
    (superseding that sprint's original "execute automatically inside a
    GET" framing): this class never mutates anything as a side effect of
    computing a proposal. `run(execute=False)` (the default) is pure
    computation — it's what backs the read-only `GET /tenants/
    auto-actions` dry-run. `run(execute=True)` is the only path that
    ever calls `auth.set_organization_plan()`/`auth.set_retention_flag()`
    /`stripe_sync.*` for real, and is only ever reachable from the
    explicit `POST /tenants/auto-actions/apply` endpoint — never from a
    GET, and never automatically on a schedule. There is no recursive/
    looping call anywhere in this class (bug #2 from Sprint 278's own
    list, "rodar upgrade infinito") — `run()` computes a proposal
    exactly once per call and, if executing, applies it exactly once;
    nothing here ever calls `run()` again on its own.

    Sprint 279 — "Stripe é a fonte da verdade para billing" (the user's
    own words): `auto_upgrade()` no longer *excludes* Stripe-bound
    organizations from its proposals the way Sprint 278 did (there's now
    a safe way to act on them — see `_apply_plan_change()` below); the
    Stripe-safety guard moved from "skip this org entirely" to "route
    this org's execution through `StripeSyncService` instead of mutating
    `plan` directly", which is what `stripe_sync` (optional, `None` when
    Stripe isn't configured — same "feature toggle" shape as
    `get_stripe_service()`) is for. An organization with `stripe_
    subscription_id` set is *never* mutated directly, with or without
    `stripe_sync` configured — if Stripe sync isn't available, that
    organization's action is skipped outright rather than falling back
    to an unsafe direct plan change.

    Sprint 281 — Sprint 280 gave customers a self-serve Stripe Customer
    Portal to manage their own subscription, including cancelling/
    downgrading it themselves. Per the user's own explicit decision:
    downgrades are *never* auto-executed anymore, full stop, whether the
    organization is Stripe-bound or not — `auto_downgrade()`'s proposals
    now only ever appear in `run()`'s `"downgrade_recommendations"`
    bucket, and are never passed to `_apply_plan_change()` at all (see
    `run()`'s own docstring). Retention flagging never touches `plan`
    at all, so it always carried no such risk and stays unaffected by
    either sprint's Stripe-routing or auto-execution changes.

    `notifier` (optional, Sprint 281, `None` by default — same
    "feature toggle, no crash" shape as `stripe_sync`) is called, when
    present, exactly three times per `run(execute=True, ...)` call at
    most per action: once per organization actually upgraded, once per
    organization whose upgrade instead produced a pending Checkout
    Session, and once per organization newly flagged for retention.
    Never called during `run(execute=False)` (the read-only dry-run) —
    a notification is an observable side effect just as much as a plan
    mutation is, and Sprint 278's "no side effects inside GET" rule
    doesn't carve out an exception for it.
    """

    def __init__(self, analytics, auth, stripe_sync=None, notifier=None):
        self.analytics = analytics
        self.auth = auth
        self.stripe_sync = stripe_sync
        self.notifier = notifier

    def auto_upgrade(self) -> list[dict]:
        """Proposes free -> pro upgrades. Pure computation — never calls
        `set_organization_plan()`/`stripe_sync.*` itself.

        Qualifies if the org is on the free plan and either:

        - `over_usage`: `alerts_sent` usage is over 100% of the free
          plan's limit (stricter than `upgrade_recommendations()`'s own
          80%-and-informational threshold — an auto-*executed* action
          warrants a higher bar than a merely-suggested one), or
        - `high_health`: health score (`BillingAnalytics.
          score_organization()`, not recalculated by hand) above 85.
          Note: under Sprint 276's fixed scoring weights, a free-plan
          org's score is capped at 60 (30 not-canceled + 20 no-failure +
          10 tenure — the paid-plan-only +40 is unreachable by
          definition for an org this method only ever considers when
          `plan == "free"`), so this branch can currently never fire —
          `over_usage` is the only path that actually triggers an
          auto-upgrade right now. Same reasoning `upgrade_recommendations()`
          already documents for its own analogous `> 80` check (Sprint
          277); not silently dropped or given an invented threshold here
          either, for the same reason.

        Sprint 278 also excluded any org with a `stripe_subscription_id`
        from this proposal entirely; Sprint 279 removed that — see this
        class's own module docstring for why. In practice this barely
        changes which orgs get proposed (a *free*-plan org with an
        *active* Stripe subscription would be a data inconsistency —
        checkout completing already sets `plan` to the paid tier — the
        realistic case is a free org with a *stale, canceled*
        subscription id left over from a past churn, which Sprint 278
        would have silently, permanently ignored forever even after this
        sprint added a safe way to act on it).
        """
        actions = []

        for org_id, org in self.auth.list_organizations().items():
            if org.get("plan", "free") != "free":
                continue

            ratio = self.analytics.usage_ratio(org_id)
            over_usage = ratio is not None and ratio > 1.0

            score = self.analytics.score_organization(org)
            high_health = score > _UPGRADE_HEALTH_THRESHOLD

            if not (over_usage or high_health):
                continue

            actions.append(
                {
                    "org_id": org_id,
                    "action": "upgrade",
                    "from": "free",
                    "to": "pro",
                    "reason": "over_usage" if over_usage else "high_health",
                }
            )

        return actions

    def auto_downgrade(self) -> list[dict]:
        """Proposes downgrade *recommendations* — never executed by
        anything in this class as of Sprint 281 (see this class's own
        module docstring: self-serve billing, Sprint 280, made this the
        customer's own exclusive path now). Pure computation — never
        calls `set_organization_plan()`/`stripe_sync.*` itself, and
        `run()` never routes this method's output to `_apply_plan_
        change()` the way it still does for `auto_upgrade()`'s.

        Qualifies if the org is on a paid plan, has existed for at least
        30 days (bug #3 from Sprint 278's own list, "downgrade sem
        checar tempo mínimo" — an org younger than that, or with no
        recorded `created_at` at all, is never a candidate: not enough
        history to judge, and a fresh signup shouldn't get flagged out
        from under it), scores under 40 (`score_organization()`), and
        shows very low usage. "Very low usage" (undefined by the spec)
        is defined here as under 10% of the plan's limit; an org with no
        usage signal at all (`usage_ratio()` returns `None`) is *not*
        treated as low-usage — the conservative default for a
        revenue-affecting recommendation about a paying customer is
        "can't confirm, don't flag", not "assume the worst".

        IMPORTANT — reachability of the score condition, still true
        after Sprints 279-281: every paid-plan org's real score has a
        floor of 60, never below 40. `score_organization()` always
        awards +40 for any `plan != "free"`, and `subscription_status`
        is a single field, so an org can only ever lose *one* of the +30
        (not-canceled) / +20 (no-payment-failure) pair, never both —
        worst case is 40 + 20 (canceled) = 60. That means this method's
        score condition can never actually be satisfied under Sprint
        276's fixed weights, so **`auto_downgrade()` still always
        returns `[]`** right now, regardless of tenure or usage. Left
        exactly as documented in Sprint 278: not silently picking a
        different threshold, since "40" isn't objectively wrong, just
        unreachable given weights no sprint since has had reason to
        revisit.
        """
        actions = []
        now = int(time.time())

        for org_id, org in self.auth.list_organizations().items():
            plan = org.get("plan", "free")

            if plan == "free":
                continue

            created_at = org.get("created_at")
            age_days = (now - created_at) / _SECONDS_PER_DAY if created_at else 0

            if age_days < _MIN_TENURE_DAYS_FOR_DOWNGRADE:
                continue

            score = self.analytics.score_organization(org)

            if score >= _DOWNGRADE_HEALTH_THRESHOLD:
                continue

            ratio = self.analytics.usage_ratio(org_id)

            if ratio is None or ratio >= _DOWNGRADE_USAGE_RATIO_THRESHOLD:
                continue

            actions.append(
                {
                    "org_id": org_id,
                    "action": "downgrade",
                    "from": plan,
                    "to": "free",
                    "reason": "low_engagement",
                }
            )

        return actions

    def auto_retention(self) -> list[dict]:
        """Proposes retention flags for high-churn-risk organizations,
        based on `BillingAnalytics.predict_churn()` (not recalculated by
        hand). Pure computation — never calls `set_retention_flag()`
        itself. No Stripe guard: flagging never touches `plan`.

        The spec's own "optional: downgrade preventivo" isn't
        implemented — a preventive downgrade is a *plan mutation*, and
        this sprint's own Stripe-safety rules explicitly restrict paid-
        plan mutations until Sprint 279; retention flagging is called
        out as safe specifically *because* it doesn't touch `plan` at
        all, so folding a downgrade into it would contradict that.
        """
        return [
            {"org_id": entry["org_id"], "action": "retention_flag", "reason": entry["reason"]}
            for entry in self.analytics.predict_churn()
            if entry["risk"] == "high"
        ]

    def _apply_plan_change(self, action: dict) -> dict:
        """The only place in this class that ever changes a plan —
        upgrades only, as of Sprint 281 (downgrades are never routed
        here at all anymore; see `run()`'s own docstring and this
        class's own module docstring). Re-checks the organization still
        exists and is still on the plan the proposal assumed — right
        before acting (bug #1 from Sprint 278's own list, "alterar plano
        sem validar existência da org") — since `run()`'s proposal could
        be stale by the time it's actually applied (another request
        could have changed the org in between the dry-run and the apply
        call).

        Returns `{"status": "applied"}` (a direct internal
        `set_organization_plan()` — no Stripe involvement at all, either
        because the org was never Stripe-bound, or Stripe sync isn't
        configured for this deployment... except when the org *is*
        Stripe-bound and sync isn't available, which is `"skipped"`
        instead — see below), `{"status": "pending", "checkout_url":
        ...}` (routed to Stripe, needs the customer to complete checkout
        — see `StripeSyncService.upgrade_subscription()`), or
        `{"status": "skipped", ...}`.

        Routing (Sprint 279, "Stripe é a fonte da verdade" — the user's
        own words): an organization with `stripe_subscription_id` set is
        *never* mutated directly here, with or without `stripe_sync`
        configured. If it's set and `stripe_sync` is `None` (Stripe
        isn't configured for this deployment at all), the action is
        skipped outright — falling back to an unsafe direct plan change
        would silently desync billed reality from in-app plan/limits,
        exactly the "revenue leak" / "customer harm" failure Sprint 279
        exists to close. `set_organization_plan()` itself already raises
        `LookupError` for a genuinely nonexistent org and already
        invalidates `PlatformAuth`'s own plan cache (Sprint 275, bug #5
        from Sprint 278's own list) — used only for the no-Stripe-
        binding path, so both are still covered without duplicating
        either.

        Defensive guard (Sprint 281): `run()` never actually passes a
        `"downgrade"` action here — `auto_downgrade()`'s output goes
        straight into `"downgrade_recommendations"` and is never routed
        through this method at all (see `run()`'s own docstring). This
        check exists anyway, as a hard floor that can't regress even if
        a future change to `run()` mistakenly wired a downgrade back in.
        """
        if action["action"] != "upgrade":
            return {"status": "skipped", "reason": "self_serve_billing_enabled"}

        org = self.auth.get_organization(action["org_id"])

        if org is None:
            return {"status": "skipped", "reason": "org_not_found"}

        if org.get("plan", "free") != action["from"]:
            return {"status": "skipped", "reason": "plan_drifted"}

        if org.get("stripe_subscription_id"):
            if self.stripe_sync is None:
                return {"status": "skipped", "reason": "stripe_not_configured"}

            return self.stripe_sync.upgrade_subscription(action["org_id"], action["to"])

        self.auth.set_organization_plan(action["org_id"], action["to"])

        return {"status": "applied"}

    def _apply_retention_flag(self, action: dict) -> bool:
        org = self.auth.get_organization(action["org_id"])

        if org is None:
            return False

        self.auth.set_retention_flag(action["org_id"], True)

        return True

    def run(
        self,
        execute: bool = False,
        org_id: str | None = None,
        action_type: str | None = None,
    ) -> dict:
        """Always recomputes the proposal fresh from current
        organization state — `{"upgrades": [...],
        "downgrade_recommendations": [...], "retention": [...]}`
        (dry-run) or, when executing, that same shape plus
        `"pending_checkout"` (Sprint 279 — see below). `org_id`/
        `action_type` (`action_type` one of `"upgrade"`, `"downgrade"`,
        `"retention_flag"`) filter which entries are included in the
        returned dict, whether or not `execute` is set — used both to
        scope a caller's *view* (an organization owner should only ever
        see their own org's proposal, never every tenant's) and to scope
        what actually gets *applied*.

        `execute=False` (the default): pure computation, returns the
        (filtered) proposal, mutates nothing, sends no notifications.

        `execute=True`: applies every (filtered) proposed **upgrade**
        action via `_apply_plan_change()`, and every retention flag via
        `_apply_retention_flag()`. Downgrade recommendations are never
        applied at all, by anything, regardless of `execute` — Sprint
        281's own explicit decision, superseding Sprints 278/279's
        execution path entirely, now that Sprint 280 gave customers a
        self-serve Stripe Customer Portal to manage this themselves.
        `"downgrade_recommendations"` in the executed response is
        exactly the same (filtered) list `auto_downgrade()` produced —
        not routed through any apply-and-check-status step the way
        `"upgrades"`/`"retention"` are, since there is no "applied"
        outcome for a downgrade to have.

        Only actions that were *actually* applied land in `"upgrades"`/
        `"retention"` — one skipped by re-validation (e.g. the org's
        state drifted since the proposal was computed, or it's
        Stripe-bound with no `stripe_sync` configured) is silently
        omitted, not included as if it had succeeded. An upgrade that
        instead created a Stripe Checkout Session (no existing active
        subscription to modify — see `StripeSyncService.
        upgrade_subscription()`) is **not** counted as applied either:
        Sprint 279's own explicit decision is that creating a checkout
        session must never be reported the same as a completed upgrade,
        since nothing about the organization's actual plan changed and
        won't until the *customer* completes it. It lands in the
        separate `"pending_checkout"` bucket instead: `{"org_id",
        "action": "upgrade", "checkout_url", "reason": "requires_
        customer_action"}` — `"action"` isn't part of the response shape
        Sprint 279 asked for, added anyway so the router's audit logging
        can treat every bucket uniformly rather than special-casing this
        one.

        `self.notifier` (Sprint 281, optional), when present, is sent
        one notification per organization actually upgraded
        (`"upgrade_recommended"`), per organization that instead got a
        pending checkout (`"checkout_pending"`), and per organization
        newly flagged for retention (`"churn_risk"`) — never for
        downgrade recommendations (not part of the spec's own 3-event
        list, and firing one for literally every recommended downgrade,
        every single time `apply()` is called, with no dedup mechanism
        in the current stub `NotificationService`, would mean repeat,
        unbounded notification spam for the exact same organization on
        every call). Never sent during a dry-run (`execute=False`) —
        the same "no side effects inside GET" rule that already governs
        plan mutations applies equally to a notification, which is
        itself an observable side effect.

        This must only ever be reached via the explicit `POST /tenants/
        auto-actions/apply` endpoint, never the read-only GET dry-run —
        Sprint 278's own explicit "no mutation inside GET" rule, which
        no sprint since has touched.
        """

        def _matches(action: dict) -> bool:
            if org_id is not None and action["org_id"] != org_id:
                return False
            if action_type is not None and action["action"] != action_type:
                return False
            return True

        proposal = {
            "upgrades": [a for a in self.auto_upgrade() if _matches(a)],
            "downgrade_recommendations": [a for a in self.auto_downgrade() if _matches(a)],
            "retention": [a for a in self.auto_retention() if _matches(a)],
        }

        if not execute:
            return proposal

        applied: dict[str, list[dict]] = {
            "upgrades": [],
            "downgrade_recommendations": proposal["downgrade_recommendations"],
            "retention": [],
            "pending_checkout": [],
        }

        for action in proposal["upgrades"]:
            result = self._apply_plan_change(action)

            if result["status"] == "applied":
                applied["upgrades"].append(action)

                if self.notifier:
                    self.notifier.send(action["org_id"], "upgrade_recommended", action)
            elif result["status"] == "pending":
                pending_entry = {
                    "org_id": action["org_id"],
                    "action": "upgrade",
                    "checkout_url": result["checkout_url"],
                    "reason": "requires_customer_action",
                }
                applied["pending_checkout"].append(pending_entry)

                if self.notifier:
                    self.notifier.send(action["org_id"], "checkout_pending", pending_entry)

        for action in proposal["retention"]:
            if self._apply_retention_flag(action):
                applied["retention"].append(action)

                if self.notifier:
                    self.notifier.send(action["org_id"], "churn_risk", action)

        return applied
