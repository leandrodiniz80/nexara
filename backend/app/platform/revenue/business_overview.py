from app.platform.billing.pricing import get_plan_price

_HIGH_PRIORITY_SCORE_THRESHOLD = 60
_MEDIUM_PRIORITY_SCORE_THRESHOLD = 30
_TOP_OPPORTUNITIES_LIMIT = 10
_TOP_CUSTOMERS_LIMIT = 10
_ACTION_FOR_PRIORITY = {"high": "contact_now", "medium": "monitor", "low": "ignore"}

# business_score weighting (Sprint 287) -- a composite of already-computed
# metrics, not a new prediction. See BusinessOverviewEngine.business_score()
# for why each weight is what it is.
_BUSINESS_SCORE_BASELINE = 50.0
_GROWTH_RATE_CAP = 25.0
_CHURN_RATE_CAP = 25.0
_CONVERSION_RATE_WEIGHT = 20.0
_RISK_RATIO_WEIGHT = 25.0
_GROWING_STATUS_THRESHOLD = 70
_STABLE_STATUS_THRESHOLD = 40


class BusinessOverviewEngine:
    """Nexara's main entry point (Sprint 286, refined into a "premium
    business intelligence layer" Sprint 287) — still a purely read-only
    aggregation over Sprints 272-285. This sprint's own explicit rule,
    "não adicionar novas análises externas", holds throughout: every
    number here is either read straight from `BillingAnalytics`/
    `RevenueActivationEngine`/`LeadExecutionTracker`, or a *composite* of
    two or more of those already-computed numbers — nothing here scans
    raw organization data to invent a new signal from scratch.

    Sprint 287 changes, all documented at their own methods:

    - `priority_score` (float) *replaces* Sprint 286's categorical
      `priority` string on every annotated entry — the same underlying
      `score_lead()` value, boosted by the organization's own real
      revenue (`get_plan_price()`, already established since Sprint
      272) so a higher-paying customer naturally outranks an equally
      "scored" free one. `recommended_action` is still derived from it,
      just directly from the number instead of through an intermediate
      3-way label.
    - `high_risk_customers` is renamed `at_risk_customers`, each entry
      gaining `revenue_at_risk` (that organization's own MRR
      contribution) — ranking churn risk by *business impact*, not just
      raw behavioral score.
    - `top_customers` (new): paying organizations ranked by their own
      real MRR contribution — no `score_lead()`/priority concept at
      all, since "who are our biggest accounts right now" isn't an
      action to take, just context.
    - `business_score`/`business_status`, `weekly_focus`, and
      `executive_insight` are new synthesis layers over everything
      above — see each method's own docstring.
    """

    def __init__(self, analytics, activation_engine, lead_tracker):
        self.analytics = analytics
        self.activation = activation_engine
        self.lead_tracker = lead_tracker

    def _priority_score(self, entry: dict, org: dict) -> float:
        revenue_boost = get_plan_price(org.get("plan", "free")) / 10

        return round(entry["score"] + revenue_boost, 1)

    def _action_for_priority_score(self, priority_score: float) -> str:
        if priority_score >= _HIGH_PRIORITY_SCORE_THRESHOLD:
            return _ACTION_FOR_PRIORITY["high"]

        if priority_score >= _MEDIUM_PRIORITY_SCORE_THRESHOLD:
            return _ACTION_FOR_PRIORITY["medium"]

        return _ACTION_FOR_PRIORITY["low"]

    def _annotate(self, entry: dict, item_type: str, org: dict) -> dict:
        priority_score = self._priority_score(entry, org)

        return {
            **entry,
            "type": item_type,
            "priority_score": priority_score,
            "recommended_action": self._action_for_priority_score(priority_score),
        }

    def top_opportunities(self, limit: int = _TOP_OPPORTUNITIES_LIMIT) -> list[dict]:
        """Combines `high_intent_leads()` and `expansion_opportunities()`
        — unchanged from Sprint 286 beyond `priority_score` replacing
        `priority` (see this class's own docstring). Not deduplicated,
        capped at `limit`, same reasoning as Sprint 286.
        """
        orgs = self.analytics.auth.list_organizations()

        combined = [
            self._annotate(entry, "high_intent", orgs.get(entry["org_id"], {}))
            for entry in self.activation.high_intent_leads()
        ] + [
            self._annotate(entry, "expansion", orgs.get(entry["org_id"], {}))
            for entry in self.activation.expansion_opportunities()
        ]

        combined.sort(key=lambda item: item["priority_score"], reverse=True)

        return combined[:limit]

    def at_risk_customers(self) -> list[dict]:
        """`churn_risk_leads()` (Sprint 283), annotated the same way as
        `top_opportunities()`'s entries, plus `revenue_at_risk` — the
        organization's own current MRR contribution (`get_plan_price()`
        on its current plan), so a $299/mo enterprise account at risk
        is visibly distinguishable from a free trial that happens to
        share the same raw churn score. Still uncapped, for the same
        reason as Sprint 286: silently hiding a genuine risk past a
        fixed cutoff is a real business risk this overview shouldn't
        introduce.
        """
        orgs = self.analytics.auth.list_organizations()
        entries = []

        for lead in self.activation.churn_risk_leads():
            org = orgs.get(lead["org_id"], {})
            annotated = self._annotate(lead, "churn_risk", org)
            annotated["revenue_at_risk"] = get_plan_price(org.get("plan", "free"))
            entries.append(annotated)

        entries.sort(key=lambda item: item["priority_score"], reverse=True)

        return entries

    def top_customers(self, limit: int = _TOP_CUSTOMERS_LIMIT) -> list[dict]:
        """Paying organizations ranked by their own current MRR
        contribution (`get_plan_price()`) — informational context
        ("who are our biggest accounts right now"), not an action list:
        there's no `score_lead()` behavioral signal backing "you have a
        big customer", so no `priority_score`/`recommended_action` is
        attached here, unlike `top_opportunities()`/`at_risk_customers()`.
        """
        customers = []

        for org_id, org in self.analytics.auth.list_organizations().items():
            plan = org.get("plan", "free")
            revenue = get_plan_price(plan)

            if revenue == 0:
                continue

            customers.append({"org_id": org_id, "plan": plan, "revenue": revenue})

        customers.sort(key=lambda customer: customer["revenue"], reverse=True)

        return customers[:limit]

    def business_score(self) -> int:
        """0-100 composite (Sprint 287) — a weighted blend of four
        already-computed signals, not a new prediction:

        - Starts at a neutral baseline of 50.
        - +/- `growth_rate()` (Sprint 273's MoM revenue growth %),
          capped at +/-25 so one anomalous cohort-revenue swing can't
          single-handedly saturate the score.
        - -`churn_rate()` (Sprint 274), capped at -25 for the same
          reason.
        - + average `conversion_summary()` rate across lead types
          (Sprint 285) * 20 — sales execution quality.
        - - the fraction of `active_customers()` that are currently
          `churn_risk_leads()` * 25 — how much of the paying base is
          at risk right now.

        These weights aren't specified anywhere upstream — documented
        as a reasonable heuristic composite, not an objectively correct
        formula, the same way earlier sprints handled their own
        undefined thresholds.
        """
        score = _BUSINESS_SCORE_BASELINE

        growth = self.analytics.growth_rate()
        score += max(-_GROWTH_RATE_CAP, min(_GROWTH_RATE_CAP, growth))

        churn = self.analytics.churn_rate()
        score -= max(0.0, min(_CHURN_RATE_CAP, churn))

        summary = self.lead_tracker.conversion_summary()
        conversion_rates = [metrics["conversion_rate"] for metrics in summary.values()]
        avg_conversion_rate = (
            sum(conversion_rates) / len(conversion_rates) if conversion_rates else 0.0
        )
        score += avg_conversion_rate * _CONVERSION_RATE_WEIGHT

        active = self.analytics.active_customers()
        risk_count = len(self.activation.churn_risk_leads())
        risk_ratio = (risk_count / active) if active else 0.0
        score -= min(risk_ratio, 1.0) * _RISK_RATIO_WEIGHT

        return round(max(0.0, min(100.0, score)))

    def business_status(self, score: int) -> str:
        if score >= _GROWING_STATUS_THRESHOLD:
            return "growing"

        if score >= _STABLE_STATUS_THRESHOLD:
            return "stable"

        return "risk"

    def weekly_focus(self) -> dict:
        """The single highest-`priority_score` item across
        `top_opportunities()` and `at_risk_customers()` combined — "if
        you only do one thing this week, do this". A plain selection
        over already-ranked data, not a new ranking algorithm.

        `{"org_id": None, ..., "message": "..."}` when there's nothing
        actionable at all, rather than `None`/an empty dict — keeps the
        response shape consistent for API consumers either way.
        """
        candidates = self.top_opportunities() + self.at_risk_customers()

        if not candidates:
            return {
                "org_id": None,
                "type": None,
                "priority_score": None,
                "recommended_action": None,
                "message": "No urgent items this week — nothing currently qualifies "
                "as a revenue opportunity or churn risk.",
            }

        top = max(candidates, key=lambda item: item["priority_score"])
        reason = top.get("reason", "")

        return {
            "org_id": top["org_id"],
            "type": top["type"],
            "priority_score": top["priority_score"],
            "recommended_action": top["recommended_action"],
            "message": f"{top['recommended_action']} on {top['org_id']} "
            f"({top['type']}, priority {top['priority_score']}"
            f"{f': {reason}' if reason else ''}).",
        }

    def executive_insight(self, business_score: int, business_status: str) -> str:
        """One deterministic, template-composed sentence over numbers
        this method doesn't compute itself — no LLM/external call
        (this sprint's own explicit "não adicionar integrações
        externas" rule), just an f-string over already-known values,
        the same "message" pattern already established in
        `SalesPlaybookEngine` (Sprint 284).
        """
        status_phrase = {
            "growing": "growing steadily",
            "stable": "holding stable",
            "risk": "showing signs of risk",
        }[business_status]

        opportunities = len(self.top_opportunities())
        risks = len(self.at_risk_customers())

        return (
            f"Business is {status_phrase} with a score of {business_score}/100. "
            f"MRR is {self.analytics.active_mrr()}, churn rate is "
            f"{self.analytics.churn_rate()}%. There "
            f"{'is' if opportunities == 1 else 'are'} {opportunities} revenue "
            f"opportunit{'y' if opportunities == 1 else 'ies'} and {risks} "
            f"at-risk customer{'' if risks == 1 else 's'} to review this week."
        )

    def generate_overview(self) -> dict:
        score = self.business_score()
        status = self.business_status(score)

        return {
            "mrr": self.analytics.active_mrr(),
            "active_customers": self.analytics.active_customers(),
            "churn_rate": self.analytics.churn_rate(),
            "business_score": score,
            "business_status": status,
            "top_opportunities": self.top_opportunities(),
            "at_risk_customers": self.at_risk_customers(),
            "top_customers": self.top_customers(),
            "conversion_summary": self.lead_tracker.conversion_summary(),
            "weekly_focus": self.weekly_focus(),
            "executive_insight": self.executive_insight(score, status),
        }
