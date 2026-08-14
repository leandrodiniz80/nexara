_HIGH_USAGE_RATIO_THRESHOLD = 0.9
_HIGH_INTENT_HEALTH_THRESHOLD = 50
_SCORE_USAGE_RATIO_THRESHOLD = 0.8
_SCORE_HEALTH_THRESHOLD = 50


class RevenueActivationEngine:
    """Read-only commercial-priority signaling (Sprint 283) — takes
    `BillingDecisionEngine`/`PricingExperimentEngine`'s "what should
    happen automatically" further into "what should a human (sales/CX)
    look at first". Nothing in this class mutates anything: no
    `plan`/`subscription_status` write, no Stripe call, not even a
    notification — every method here only ever reads through
    `self.analytics` (and `self.analytics.auth`, deliberately public on
    `BillingAnalytics` for exactly this kind of composition, the same
    way `BillingDecisionEngine` already reads both `analytics.auth` and
    plain `auth`).
    """

    def __init__(self, analytics):
        self.analytics = analytics

    def score_lead(self, org_id: str, org: dict, churn_risk: str | None = None) -> int:
        """0-100ish additive score (can go negative — see below), per
        this sprint's own weight table: +40 for high usage, +30 for a
        healthy score, -30 for high churn risk, +20 for already being on
        a paid plan.

        `churn_risk` (Sprint 283, not part of the spec's own bare `def
        score_lead(self, org)` signature) is accepted as an *optional*
        precomputed value rather than recalculated here via
        `analytics.predict_churn()` — that method scans every
        organization on the platform, so recomputing it once per scored
        lead (as the spec's own bare signature would force, since it
        gives this method no other way to know an org's churn risk)
        turns an O(N) scoring pass into O(N²). Callers (the three
        `*_leads()`/`expansion_opportunities()` methods below) compute
        `predict_churn()` exactly once and pass each org's own risk in.
        `None` (the default) means "not evaluated" and applies no
        penalty, not "definitely low risk".

        Thresholds — undefined by the spec's own weight table beyond the
        point values themselves:

        - "usage_ratio" (+40) uses `> 0.8`, matching `upgrade_
          recommendations()`'s own established "high usage" bar (Sprint
          277), not this sprint's separate `> 0.9` "high_intent_leads()"
          filter threshold — a deliberately different, lower bar here,
          since scoring is meant to differentiate *among* leads, not
          gate which ones qualify as leads in the first place.
        - "health_score" (+30) uses `> 50`, matching `_RISK_THRESHOLD`,
          this codebase's own established health/risk boundary (Sprint
          276) between "risk" and "critical".
        - "churn_risk" (-30) only fires for `"high"` — `predict_churn()`'s
          own highest category (Sprint 277); there's no `"probability"`
          field anywhere in this codebase's churn model for a `> 0.7`
          check to apply to (see this class's own module-level note and
          `churn_risk_leads()`'s own docstring).
        - "plano pago" (+20) uses `plan != "free"`, this file's own
          established definition of "paying" throughout `billing_
          analytics.py`.
        """
        score = 0

        ratio = self.analytics.usage_ratio(org_id)
        if ratio is not None and ratio > _SCORE_USAGE_RATIO_THRESHOLD:
            score += 40

        if self.analytics.score_organization(org) > _SCORE_HEALTH_THRESHOLD:
            score += 30

        if churn_risk == "high":
            score -= 30

        if org.get("plan", "free") != "free":
            score += 20

        return score

    def high_intent_leads(self) -> list[dict]:
        """Organizations likely ready to upgrade right now:
        `usage_ratio > 0.9`, health score `> 50`, and not already on the
        top ("alto") paid tier — "enterprise" specifically, not "any
        paid plan": a "pro" organization can still be a high-intent lead
        for an enterprise upgrade, it's only the tier with nowhere left
        to go that's excluded. Sorted by `score_lead()`, highest first
        (this sprint's own explicit "priorização automática" rule).
        """
        churn_by_org = {entry["org_id"]: entry["risk"] for entry in self.analytics.predict_churn()}
        leads = []

        for org_id, org in self.analytics.auth.list_organizations().items():
            if org.get("plan", "free") == "enterprise":
                continue

            ratio = self.analytics.usage_ratio(org_id)
            if ratio is None or ratio <= _HIGH_USAGE_RATIO_THRESHOLD:
                continue

            health_score = self.analytics.score_organization(org)
            if health_score <= _HIGH_INTENT_HEALTH_THRESHOLD:
                continue

            leads.append(
                {
                    "org_id": org_id,
                    "plan": org.get("plan", "free"),
                    "usage_ratio": ratio,
                    "health_score": health_score,
                    "score": self.score_lead(org_id, org, churn_by_org.get(org_id)),
                }
            )

        leads.sort(key=lambda lead: lead["score"], reverse=True)

        return leads

    def churn_risk_leads(self) -> list[dict]:
        """High-churn-risk organizations, straight from `analytics.
        predict_churn()` (not recalculated by hand — this sprint's own
        explicit instruction), each with a `score_lead()` score attached
        and sorted highest first.

        The spec's own filter, "probability > 0.7", references a field
        that doesn't exist anywhere in this codebase — `predict_churn()`
        returns a categorical `risk` (`"high"`/`"medium"`/`"low"`), never
        a numeric probability (see `score_lead()`'s own docstring for
        the same point). Filters on `risk == "high"` instead — that
        method's own highest, most specific category, matching the
        clear intent of ">"" a high bar" even though the literal
        threshold doesn't apply to this data model.
        """
        orgs = self.analytics.auth.list_organizations()
        leads = []

        for entry in self.analytics.predict_churn():
            if entry["risk"] != "high":
                continue

            org = orgs.get(entry["org_id"], {})

            leads.append(
                {
                    "org_id": entry["org_id"],
                    "risk": entry["risk"],
                    "reason": entry["reason"],
                    "score": self.score_lead(entry["org_id"], org, entry["risk"]),
                }
            )

        leads.sort(key=lambda lead: lead["score"], reverse=True)

        return leads

    def expansion_opportunities(self) -> list[dict]:
        """Free-plan organizations worth nudging toward "pro", straight
        from `analytics.upgrade_recommendations()` (Sprint 277, not
        recalculated by hand), each with a `score_lead()` score attached
        and sorted highest first.
        """
        churn_by_org = {entry["org_id"]: entry["risk"] for entry in self.analytics.predict_churn()}
        orgs = self.analytics.auth.list_organizations()
        leads = []

        for entry in self.analytics.upgrade_recommendations():
            org = orgs.get(entry["org_id"], {})

            leads.append(
                {
                    **entry,
                    "score": self.score_lead(
                        entry["org_id"], org, churn_by_org.get(entry["org_id"])
                    ),
                }
            )

        leads.sort(key=lambda lead: lead["score"], reverse=True)

        return leads
