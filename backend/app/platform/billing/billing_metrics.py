from app.platform.billing.pricing import get_plan_price


class BillingMetrics:
    """SaaS-wide financial rollup (Sprint 272) — derived entirely from
    `PlatformAuth`'s persisted organization/plan state, no Stripe runtime
    calls and no separate billing store.

    Reads organizations via `auth.list_organizations()`, a new public
    method, rather than the spec's own `getattr(self._auth,
    "_organizations", {})` — reaching into `PlatformAuth`'s private state
    from outside the class is exactly what this codebase's established
    convention (public delegation methods, never `_private` access from
    callers) forbids everywhere else.
    """

    def __init__(self, auth):
        self._auth = auth

    def calculate(self) -> dict:
        orgs = self._auth.list_organizations()
        total = len(orgs)
        active = 0
        canceled = 0
        revenue = 0

        for data in orgs.values():
            plan = data.get("plan", "free")
            status = data.get("subscription_status", "active")

            if plan != "free":
                active += 1
                revenue += get_plan_price(plan)

            if status == "canceled":
                canceled += 1

        mrr = revenue
        arr = mrr * 12
        # Churn is measured against *all* organizations, not just paying
        # ones — a deliberate choice from this sprint's own spec: churn
        # should reflect how much of the whole customer base is lost, not
        # just how much of the currently-paying base is.
        churn_rate = (canceled / total) if total else 0
        arpu = (mrr / active) if active else 0
        ltv = (arpu / churn_rate) if churn_rate else 0

        return {
            "mrr": mrr,
            "arr": arr,
            "active_customers": active,
            "total_customers": total,
            "churn_rate": churn_rate,
            "arpu": arpu,
            "ltv": ltv,
        }
