import time
from collections import defaultdict
from datetime import datetime, timezone

from app.platform.billing.pricing import get_plan_price
from app.platform.billing.pricing_experiments import PricingExperimentEngine

_SECONDS_PER_DAY = 86400
_HEALTHY_THRESHOLD = 80
_RISK_THRESHOLD = 50
_ANOMALY_THRESHOLD_PCT = 30
_PRICE_UP_CONVERSION_TOLERANCE = 0.0
_PRICE_DOWN_CONVERSION_LIFT_THRESHOLD = 1.2
_CONFIDENCE_SAMPLE_SIZE = 50


def _shift_month(month: str, delta: int) -> str:
    """Adds `delta` months to a "YYYY-MM" string, used by
    `forecast_mrr()` to project forward from `revenue_timeseries()`'s
    own month keys."""
    year, month_num = (int(part) for part in month.split("-"))
    total = year * 12 + (month_num - 1) + delta

    return f"{total // 12}-{(total % 12) + 1:02d}"


class BillingAnalytics:
    """Time-based billing intelligence (Sprint 273) — revenue-by-signup-
    month, MoM growth, plan distribution, churn-by-month. All derived
    from `PlatformAuth.list_organizations()` only, same "no Stripe
    runtime, no separate store" constraint as `BillingMetrics` (Sprint
    272).

    `revenue_timeseries()` buckets by each organization's *signup* month
    (`created_at`), not a running MRR balance as of each month — this
    codebase has no historical revenue ledger to reconstruct "MRR as it
    stood in March" from, only each organization's *current* plan/status.
    Bucketing by signup month is the one interpretation this data
    actually supports, and it matches this sprint's own stated "cohort
    simples (retenção por mês de entrada)" goal — read it as
    revenue-by-acquisition-cohort, not a recurring-revenue trend line.
    """

    def __init__(self, auth, get_usage=None):
        """`get_usage` (Sprint 277): an optional `(org_id, metric) -> int`
        callable, same injected-callable shape as `resolve_tenant`/
        `get_alert_limit` (Sprint 258/265) and `UsageAlerts` (Sprint 271)
        — see `get_billing_analytics()`'s own docstring in
        app/api/dependencies/billing.py. `None` (the default) means
        `upgrade_recommendations()` simply can't see usage data and falls
        back to its other criterion, rather than crashing — every other
        caller of this class (existing tests, `BillingMetrics`-style
        usage) is unaffected by this new, optional parameter.
        """
        self.auth = auth
        self._get_usage = get_usage

    def revenue_timeseries(self) -> list[dict]:
        """Monthly revenue aggregated by organization signup month:
        [{"month": "2026-01", "revenue": 12300}, ...].

        Two real bugs in the spec's own version, fixed here:

        1. `for org in orgs:` — `list_organizations()` returns a `dict`
           keyed by org_id (`{org_id: org_data}`), matching every other
           `PlatformAuth` collection in this codebase (`_users`,
           `_organizations`). Iterating a dict yields its *keys* (plain
           org-id strings), not the org records — `org.get("created_at")`
           on a string would raise `AttributeError` on the very first
           real organization. Iterates `.values()` instead.
        2. `datetime.fromisoformat(created)` — `create_organization()`
           stores `created_at` as `int(time.time())`, a Unix timestamp,
           never an ISO string; `fromisoformat()` would raise `TypeError`
           on every real record. Uses `datetime.fromtimestamp(created,
           tz=timezone.utc)` instead.
        """
        orgs = self.auth.list_organizations()
        buckets: dict[str, int] = defaultdict(int)

        for org in orgs.values():
            created = org.get("created_at")
            if not created:
                continue

            dt = datetime.fromtimestamp(created, tz=timezone.utc)
            key = f"{dt.year}-{dt.month:02d}"

            plan = org.get("plan", "free")
            price = get_plan_price(plan)

            buckets[key] += price

        return [{"month": k, "revenue": buckets[k]} for k in sorted(buckets.keys())]

    def growth_rate(self) -> float:
        """Month-over-month change (%) between the two most recent
        buckets of `revenue_timeseries()`."""
        series = self.revenue_timeseries()

        if len(series) < 2:
            return 0.0

        last = series[-1]["revenue"]
        prev = series[-2]["revenue"]

        if prev == 0:
            return 0.0

        return round(((last - prev) / prev) * 100, 2)

    def plan_distribution(self) -> dict[str, int]:
        """Count of organizations per plan. Fixes the same `for org in
        list_organizations():` key-vs-value bug as `revenue_timeseries()`
        — see its docstring, point 1.
        """
        counts: dict[str, int] = defaultdict(int)

        for org in self.auth.list_organizations().values():
            counts[org.get("plan", "free")] += 1

        return dict(counts)

    def churn_over_time(self) -> list[dict]:
        """Monthly cancellation counts: [{"month": ..., "churned": ...}].

        Same key-vs-value iteration bug fixed as the two methods above.
        Also relies on `canceled_at`, a field nothing in this codebase
        ever wrote before this sprint — `PlatformAuth.set_subscription_
        status()` now stamps it whenever `status == "canceled"` (see its
        own docstring), the single point both Stripe cancellation event
        types funnel through.
        """
        buckets: dict[str, int] = defaultdict(int)

        for org in self.auth.list_organizations().values():
            if org.get("subscription_status") != "canceled":
                continue

            canceled_at = org.get("canceled_at")
            if not canceled_at:
                continue

            dt = datetime.fromtimestamp(canceled_at, tz=timezone.utc)
            key = f"{dt.year}-{dt.month:02d}"

            buckets[key] += 1

        return [{"month": k, "churned": buckets[k]} for k in sorted(buckets.keys())]

    def active_mrr(self) -> int:
        """Monthly recurring revenue from currently-active subscribers
        (Sprint 274) — as opposed to `revenue_timeseries()`'s
        signup-cohort view, this is a live snapshot of current revenue.

        Missing `subscription_status` (the pre-Stripe "manual upgrade"
        fallback in `/billing/upgrade` sets a plan directly via
        `set_organization_plan()` and never touches
        `subscription_status` at all) defaults to `"active"` here, not
        excluded — the same default `BillingMetrics.calculate()` already
        established (Sprint 272). Without it, every manually-upgraded
        paying organization with no Stripe-driven status would silently
        report zero revenue, contradicting `/billing/dashboard`'s own MRR
        figure for the exact same data.
        """
        total = 0

        for org in self.auth.list_organizations().values():
            if org.get("subscription_status", "active") not in ("active", "trialing"):
                continue

            plan = org.get("plan", "free")
            total += get_plan_price(plan)

        return total

    def arr(self) -> int:
        return self.active_mrr() * 12

    def active_customers(self) -> int:
        """Count of currently-*paying* subscribers (Sprint 274).

        Two fixes versus the spec's own version, both needed to stay
        consistent with `/billing/dashboard`'s own `active_customers`
        (`BillingMetrics`, Sprint 272), which counts paying (`plan !=
        "free"`) organizations:

        1. Requires `plan != "free"` — the spec's own version counted
           *any* organization with an active-ish status, with no plan
           check at all. Since a free-plan signup never goes through the
           Stripe flow that sets `subscription_status`, the missing-
           status-defaults-to-"active" fix below would otherwise count
           essentially every free signup on the platform as an "active
           customer" — a different, much larger number than
           `/billing/dashboard` reports for the same underlying data.
        2. Same missing-`subscription_status`-defaults-to-`"active"` fix
           as `active_mrr()`, for the same reason (the manual-upgrade
           fallback path).
        """
        return sum(
            1
            for org in self.auth.list_organizations().values()
            if org.get("plan", "free") != "free"
            and org.get("subscription_status", "active") in ("active", "trialing")
        )

    def churn_rate(self) -> float:
        """% of organizations with `subscription_status == "canceled"`,
        over the total organization base (paying and free alike) — same
        "churn measured against the whole base" convention already
        established in `BillingMetrics.calculate()` (Sprint 272)."""
        orgs = list(self.auth.list_organizations().values())

        if not orgs:
            return 0.0

        churned = sum(1 for o in orgs if o.get("subscription_status") == "canceled")

        return round((churned / len(orgs)) * 100, 2)

    def ltv(self) -> float:
        """Simple churn-based LTV: ARPU / churn_rate, with a 12-month
        fallback when churn is 0 (nothing to divide by, and "infinite
        lifetime" isn't a useful number to show)."""
        active = self.active_customers()
        if active == 0:
            return 0.0

        revenue = self.active_mrr()
        arpu = revenue / active

        churn = self.churn_rate() / 100

        if churn == 0:
            return round(arpu * 12, 2)

        return round(arpu / churn, 2)

    def revenue_by_plan(self) -> dict[str, int]:
        """Current revenue segmented by plan (Sprint 275) — same
        active-or-trialing, missing-status-defaults-to-active rules as
        `active_mrr()`, so this sums to the same total.

        One fix versus the spec's own version: it checked
        `org.get("plan") == "free"` and later used `org.get("plan")`
        again (no default) as the dict key. An organization record with
        no `plan` key at all (shouldn't normally happen — every real one
        gets `"plan": "free"` from `create_organization()` — but nothing
        stops a caller from passing a bare `{}`, as this file's own tests
        do to check defaults) would fail that `== "free"` check, fall
        through, and add a spurious `None` key to the result with a
        `get_plan_price(None)` price of 0. Defaulting to `"free"` here
        matches every other plan-reading method in this file.
        """
        result: dict[str, int] = {}

        for org in self.auth.list_organizations().values():
            plan = org.get("plan", "free")

            if plan == "free":
                continue

            if org.get("subscription_status", "active") not in ("active", "trialing"):
                continue

            price = get_plan_price(plan)
            result[plan] = result.get(plan, 0) + price

        return result

    def expansion_revenue(self) -> int:
        """Total revenue gained from upgrades, reconstructed from each
        organization's `plan_history` (Sprint 275, `PlatformAuth.
        set_organization_plan()`) — absent entirely on organizations that
        never changed plans, per this sprint's own "use plan_history only
        when it exists" rule."""
        total = 0

        for org in self.auth.list_organizations().values():
            for event in org.get("plan_history", []):
                old_price = get_plan_price(event["from"])
                new_price = get_plan_price(event["to"])

                if new_price > old_price:
                    total += new_price - old_price

        return total

    def contraction_revenue(self) -> int:
        """Total revenue lost to downgrades — same `plan_history` source
        as `expansion_revenue()`."""
        total = 0

        for org in self.auth.list_organizations().values():
            for event in org.get("plan_history", []):
                old_price = get_plan_price(event["from"])
                new_price = get_plan_price(event["to"])

                if new_price < old_price:
                    total += old_price - new_price

        return total

    def net_revenue_change(self) -> int:
        return self.expansion_revenue() - self.contraction_revenue()

    def forecast_mrr(self, months: int = 3) -> list[dict]:
        """Projects future revenue by continuing `revenue_timeseries()`'s
        own trend forward (Sprint 276) — the average month-over-month
        growth rate across its last up-to-3 buckets, compounded forward
        from the last known month.

        Inherits `revenue_timeseries()`'s own documented limitation:
        that series is signup-cohort revenue, not a true recorded MRR
        history (this codebase has no such ledger — see that method's
        own docstring), so this is a projection of *cohort revenue
        growth*, not a rigorous MRR forecast. Named `projected_mrr`
        because that's what this sprint asked for; the caveat is
        unavoidable given what data actually exists to project from.

        Growth rate is the average of the pairwise % changes across the
        last 3 data points (2 growth samples) — or fewer if less history
        exists. Any pair whose earlier value is 0 is skipped (a 0 base
        makes "% growth" undefined, not "0% growth"; the two aren't the
        same and conflating them would understate a real jump from
        nothing). With fewer than 2 usable samples, growth defaults to
        0% (this sprint's own explicit rule), and the forecast is flat.
        With no historical data at all, there's nothing to project
        forward from — returns `[]`.
        """
        series = self.revenue_timeseries()

        if not series:
            return []

        recent = series[-3:]
        rates = []

        for i in range(1, len(recent)):
            prev_revenue = recent[i - 1]["revenue"]
            curr_revenue = recent[i]["revenue"]

            if prev_revenue == 0:
                continue

            rates.append((curr_revenue - prev_revenue) / prev_revenue)

        growth_rate = sum(rates) / len(rates) if rates else 0.0

        projections = []
        month = series[-1]["month"]
        revenue = series[-1]["revenue"]

        for _ in range(months):
            month = _shift_month(month, 1)
            revenue = round(revenue * (1 + growth_rate))
            projections.append({"month": month, "projected_mrr": revenue})

        return projections

    def customer_health_score(self) -> dict:
        """Per-organization health score, 0-100 (Sprint 276): +40 for a
        paid plan, +30 for not being canceled, +20 for no payment
        failure (`subscription_status != "past_due"`), +10 for a
        30+ day-old signup. Same missing-`subscription_status`-defaults-
        to-`"active"` and missing-`plan`-defaults-to-`"free"`
        conventions as every other method in this file.

        Returns `{"average_score": ..., "distribution": {"healthy":
        ..., "risk": ..., "critical": ...}}` across every organization
        on the platform — `average_score: 0` and an all-zero
        distribution when there are none, rather than dividing by zero.
        """
        orgs = list(self.auth.list_organizations().values())

        if not orgs:
            return {
                "average_score": 0,
                "distribution": {"healthy": 0, "risk": 0, "critical": 0},
            }

        now = int(time.time())
        distribution = {"healthy": 0, "risk": 0, "critical": 0}
        scores = []

        for org in orgs:
            score = self._score_organization(org, now)
            scores.append(score)

            if score >= _HEALTHY_THRESHOLD:
                distribution["healthy"] += 1
            elif score >= _RISK_THRESHOLD:
                distribution["risk"] += 1
            else:
                distribution["critical"] += 1

        return {
            "average_score": round(sum(scores) / len(scores)),
            "distribution": distribution,
        }

    def _score_organization(self, org: dict, now: int) -> int:
        """The scoring formula `customer_health_score()` applies per
        organization, extracted (Sprint 277) so `predict_churn()` can
        reuse the exact same score instead of recalculating it by hand
        — this sprint's own explicit rule. Pure refactor: behavior is
        identical to what `customer_health_score()` computed inline
        before this sprint; no scoring logic changed.
        """
        score = 0

        if org.get("plan", "free") != "free":
            score += 40

        status = org.get("subscription_status", "active")

        if status != "canceled":
            score += 30

        if status != "past_due":
            score += 20

        created_at = org.get("created_at")
        if created_at and (now - created_at) > 30 * _SECONDS_PER_DAY:
            score += 10

        return score

    def score_organization(self, org: dict) -> int:
        """Public wrapper around `_score_organization()` (Sprint 278) —
        `BillingDecisionEngine.auto_upgrade()`/`auto_downgrade()` need an
        org's health score too, and reaching into this class's own
        private `_score_organization()` from outside would repeat the
        exact encapsulation break this codebase's convention forbids
        everywhere else.
        """
        return self._score_organization(org, int(time.time()))

    def usage_ratio(
        self, org_id: str, usage_metric: str = "alerts_sent", limit_metric: str = "alerts_per_hour"
    ) -> float | None:
        """Fraction of the plan limit currently used (e.g. `0.85` ==
        85%), or `None` when there's no usage source configured or no
        finite limit to compare against (`-1` unlimited, or a `0`/
        missing limit). Extracted (Sprint 278, from what
        `upgrade_recommendations()`'s own inline check used to do) so
        `upgrade_recommendations()` and `BillingDecisionEngine.
        auto_upgrade()`/`auto_downgrade()` all share one place that
        knows how to read usage safely, instead of each reimplementing
        the same `None`/`-1`/`0` guards.
        """
        if self._get_usage is None:
            return None

        limit = self.auth.get_usage_limit(org_id, limit_metric)

        if limit in (None, -1, 0):
            return None

        used = self._get_usage(org_id, usage_metric)

        return used / limit

    def detect_revenue_anomalies(self) -> list[dict]:
        """Flags month-over-month swings in `revenue_timeseries()`
        greater than 30% in either direction (Sprint 276) —
        `{"month", "change", "type": "drop" | "spike"}`. The first month
        has no prior month to compare against and is always skipped
        (this sprint's own explicit rule), and a month whose prior
        revenue was 0 is skipped too — the same division-by-zero
        guard `forecast_mrr()` needs, for the same reason: "% change
        from 0" isn't a meaningful number, so it isn't reported as one.
        """
        series = self.revenue_timeseries()
        anomalies = []

        for i in range(1, len(series)):
            prev_revenue = series[i - 1]["revenue"]
            curr_revenue = series[i]["revenue"]

            if prev_revenue == 0:
                continue

            change = round(((curr_revenue - prev_revenue) / prev_revenue) * 100, 2)

            if abs(change) > _ANOMALY_THRESHOLD_PCT:
                anomalies.append(
                    {
                        "month": series[i]["month"],
                        "change": change,
                        "type": "drop" if change < 0 else "spike",
                    }
                )

        return anomalies

    def predict_churn(self) -> list[dict]:
        """Per-organization churn-risk classification (Sprint 277):
        `[{"org_id", "risk": "high"|"medium"|"low", "reason"}, ...]`.

        Priority order, matching this sprint's own rule table exactly
        (checked top to bottom — an org can match more than one
        condition, e.g. `past_due` *and* a health score under 50, in
        which case the higher-priority row wins):

        1. `past_due` -> high / payment_failed
        2. health score < 50 (via `_score_organization()`, not
           recalculated by hand — this sprint's own explicit rule) ->
           medium / low_health
        3. free plan, signed up over 60 days ago -> medium / inactive_free
        4. everything else -> low / healthy

        Iterates `.items()`, not `.values()` — every other method in
        this file uses `.values()` because it never needs the org_id
        itself, but this one's own required output shape includes
        `org_id`, which `.values()` alone would discard.
        """
        now = int(time.time())
        results = []

        for org_id, org in self.auth.list_organizations().items():
            status = org.get("subscription_status", "active")
            plan = org.get("plan", "free")
            created_at = org.get("created_at")
            age_days = (now - created_at) / _SECONDS_PER_DAY if created_at else 0
            score = self._score_organization(org, now)

            if status == "past_due":
                risk, reason = "high", "payment_failed"
            elif score < _RISK_THRESHOLD:
                risk, reason = "medium", "low_health"
            elif plan == "free" and age_days > 60:
                risk, reason = "medium", "inactive_free"
            else:
                risk, reason = "low", "healthy"

            results.append({"org_id": org_id, "risk": risk, "reason": reason})

        return results

    def upgrade_recommendations(self) -> list[dict]:
        """Free-plan organizations worth nudging toward `"pro"` (Sprint
        277): `[{"org_id", "current_plan": "free", "recommended_plan":
        "pro", "reason"}, ...]`.

        Two criteria, either one qualifying (`"reason"` is whichever
        matched; `high_usage` takes priority when both do):

        1. `high_usage` — `alerts_sent` at/above 80% of the free plan's
           `alerts_per_hour` limit, read via `usage_ratio()` (Sprint
           278's public extraction of this exact check — see its own
           docstring). `None` (no usage source configured, or an
           unlimited/zero/missing limit) degrades to "no usage signal"
           rather than crashing.
        2. `high_health` — health score (via `score_organization()`,
           not recalculated by hand) above 80. Included for
           completeness, but note this can *never actually fire*: a
           free-plan org's score is capped at 60 (30 for not-canceled +
           20 for no payment failure + 10 for 30+ day tenure — the paid-
           plan-only +40 is unreachable by definition for an org that
           passed this method's own `plan == "free"` filter). Flagging
           this rather than silently dropping the criterion, since
           "always false" is a materially different thing from "correct
           but rarely true", and changing the threshold to something
           reachable would be inventing a business rule the spec never
           actually specified.
        """
        recommendations = []

        for org_id, org in self.auth.list_organizations().items():
            plan = org.get("plan", "free")

            if plan != "free":
                continue

            ratio = self.usage_ratio(org_id)
            high_usage = ratio is not None and ratio >= 0.8

            score = self.score_organization(org)
            high_health = score > _HEALTHY_THRESHOLD

            if not (high_usage or high_health):
                continue

            recommendations.append(
                {
                    "org_id": org_id,
                    "current_plan": "free",
                    "recommended_plan": "pro",
                    "reason": "high_usage" if high_usage else "high_health",
                }
            )

        return recommendations

    def predicted_ltv(self) -> float:
        """Churn-risk-adjusted LTV (Sprint 277): starts from `ltv()`'s
        aggregate figure (Sprint 274) and discounts it per organization
        by that organization's own churn risk (`predict_churn()`, not
        recalculated by hand) — high risk -40%, medium -20%, low 0% —
        then averages those adjusted figures back into a single number,
        weighted by each organization's own MRR contribution
        (`get_plan_price(plan)`).

        The spec asked for a "weighted average of customers" without
        specifying what the weight should be; MRR contribution is the
        one available number that actually reflects how much each
        customer matters to revenue (the same quantity `arpu`/`mrr`
        already key off elsewhere in this file) — an unweighted average
        would let a free trial and an enterprise account pull the
        figure by an equal amount, which doesn't match what "LTV"
        is supposed to represent in the first place.

        Free-plan organizations (zero MRR weight) don't affect this
        figure at all. Returns `0.0` immediately when the base `ltv()`
        is already `0.0` (nothing to adjust), and falls back to the
        unadjusted base if there happen to be no paying organizations to
        weight by (mirrors `ltv()`'s own zero-active-customers case).
        """
        base_ltv = self.ltv()

        if base_ltv == 0:
            return 0.0

        risk_discount = {"high": 0.4, "medium": 0.2, "low": 0.0}
        orgs = self.auth.list_organizations()

        weighted_total = 0.0
        weight_sum = 0

        for entry in self.predict_churn():
            org = orgs.get(entry["org_id"], {})
            weight = get_plan_price(org.get("plan", "free"))

            if weight == 0:
                continue

            discount = risk_discount.get(entry["risk"], 0.0)
            adjusted = base_ltv * (1 - discount)

            weighted_total += adjusted * weight
            weight_sum += weight

        if weight_sum == 0:
            return round(base_ltv, 2)

        return round(weighted_total / weight_sum, 2)

    def pricing_experiment_metrics(self) -> dict:
        """Per-variant simulation metrics (Sprint 282):
        `{"control": {"conversion_rate", "mrr"}, "price_up": {...},
        "price_down": {...}}`. Every organization is deterministically
        assigned to exactly one variant (`PricingExperimentEngine.
        assign_variant()`, constructed fresh here — stateless, so no
        constructor injection needed on this class for it).

        `conversion_rate` is the *real, observed* fraction of each
        variant's organizations currently on a paid plan (`plan !=
        "free"`, this file's own established definition of "paying" —
        see `active_customers()`) — nothing here has actually changed
        any organization's real price, so this reflects genuine current
        behavior, not a prediction.

        `mrr` is *simulated*: for each paying organization, `get_plan_
        price(plan)` run through `PricingExperimentEngine.
        get_price_for_org()` — i.e. "what this organization's current
        plan would cost under this variant's price adjustment", summed
        per group. This is the one number in this method that is
        hypothetical rather than observed, since (per this sprint's own
        explicit rule) nothing here has actually changed real billing —
        Stripe still charges everyone the same, unmodified price.
        """
        engine = PricingExperimentEngine(self.auth)
        totals = {variant: 0 for variant in ("control", "price_up", "price_down")}
        paying = {variant: 0 for variant in ("control", "price_up", "price_down")}
        mrr = {variant: 0.0 for variant in ("control", "price_up", "price_down")}

        for org_id, org in self.auth.list_organizations().items():
            variant = engine.assign_variant(org_id)
            totals[variant] += 1

            plan = org.get("plan", "free")
            base_price = get_plan_price(plan)

            if base_price == 0:
                continue

            paying[variant] += 1
            mrr[variant] += engine.get_price_for_org(org_id, base_price)

        return {
            variant: {
                "conversion_rate": round(paying[variant] / totals[variant], 4)
                if totals[variant]
                else 0.0,
                "mrr": round(mrr[variant], 2),
            }
            for variant in ("control", "price_up", "price_down")
        }

    def recommend_price_adjustment(self) -> dict:
        """`{"recommended_strategy": "increase"|"decrease"|"keep",
        "confidence": float, "reason": str}`, derived from
        `pricing_experiment_metrics()` (not recalculated by hand).

        Neither the exact meaning of "sem cair conversão" nor "aumenta
        muito conversão" nor how to compute "confidence" was specified
        by the spec — this is a pure analytics/recommendation surface
        with no execution attached to it at all (this sprint's own
        explicit "zero side-effect" rule), so the choices below are
        documented rather than treated as objectively correct:

        - `"increase"`: `price_up`'s simulated MRR beats `control`'s
          real MRR, and `price_up`'s real conversion rate is at least
          `control`'s (no drop at all — the literal "sem cair").
        - `"decrease"`: `price_down`'s real conversion rate beats
          `control`'s by at least 20% relatively (`>= control * 1.2` —
          "aumenta muito", a deliberately higher bar than "increase"'s
          "no drop", since cutting price is the more expensive mistake
          to get wrong if conversion doesn't actually respond).
        - `"keep"`: neither condition holds. Checked in that order —
          `"increase"` wins if both conditions happen to hold at once,
          since more revenue with flat-or-better conversion is the
          least ambiguous positive signal available here.

        `confidence` is a simple, explicitly-labeled heuristic — the
        deciding group's organization count divided by 50 (capped at
        1.0), *not* a real statistical significance test (no chi-square/
        t-test infrastructure exists here, and building one wasn't asked
        for). `0.0` for `"keep"`: there's no single "deciding group" to
        size confidence off of when neither threshold was met.
        """
        metrics = self.pricing_experiment_metrics()
        orgs = self.auth.list_organizations()

        control = metrics["control"]
        price_up = metrics["price_up"]
        price_down = metrics["price_down"]

        price_up_conversion_floor = control["conversion_rate"] - _PRICE_UP_CONVERSION_TOLERANCE

        if price_up["mrr"] > control["mrr"] and price_up["conversion_rate"] >= (
            price_up_conversion_floor
        ):
            engine = PricingExperimentEngine(self.auth)
            group_size = sum(1 for org_id in orgs if engine.assign_variant(org_id) == "price_up")

            return {
                "recommended_strategy": "increase",
                "confidence": round(min(1.0, group_size / _CONFIDENCE_SAMPLE_SIZE), 2),
                "reason": "price_up generates more MRR without a drop in conversion rate",
            }

        if control["conversion_rate"] > 0 and price_down["conversion_rate"] >= (
            control["conversion_rate"] * _PRICE_DOWN_CONVERSION_LIFT_THRESHOLD
        ):
            engine = PricingExperimentEngine(self.auth)
            group_size = sum(
                1 for org_id in orgs if engine.assign_variant(org_id) == "price_down"
            )

            return {
                "recommended_strategy": "decrease",
                "confidence": round(min(1.0, group_size / _CONFIDENCE_SAMPLE_SIZE), 2),
                "reason": "price_down meaningfully increases conversion rate",
            }

        return {
            "recommended_strategy": "keep",
            "confidence": 0.0,
            "reason": "no variant shows a clear improvement over control",
        }
