"""Tests for BillingDecisionEngine's Sprint 279 Stripe-routing behavior:
a Stripe-bound organization's plan is never mutated directly, always
routed through StripeSyncService instead, and Sprint 278's own
eligibility guards (tenure, score, usage) still apply regardless of
routing.

Sprint 281 note: this file originally also covered Stripe-bound
*downgrade* routing (StripeSyncService.downgrade_subscription() being
called and counted as "applied"). That entire path was removed this
sprint -- downgrades are never executed by anything, Stripe-bound or
not (self-serve billing, Sprint 280, made this the customer's own
exclusive path) -- so those tests were replaced with regression guards
proving `downgrade_subscription()` is never called at all, rather than
testing how its result was handled.
"""

import time

from app.platform.billing.decision_engine import BillingDecisionEngine

_DAY = 86400


def _days_ago(n: int) -> int:
    return int(time.time()) - n * _DAY


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs
        self.plan_changes: list[tuple[str, str]] = []

    def list_organizations(self) -> dict:
        return dict(self._orgs)

    def get_organization(self, org_id: str) -> dict | None:
        return self._orgs.get(org_id)

    def set_organization_plan(self, org_id: str, plan: str) -> None:
        org = self._orgs.get(org_id)
        if org is None:
            raise LookupError(org_id)
        org["plan"] = plan
        self.plan_changes.append((org_id, plan))

    def set_retention_flag(self, org_id: str, flag: bool) -> None:
        pass


class FakeAnalytics:
    def __init__(self, usage_ratios: dict | None = None, scores: dict | None = None):
        self._usage_ratios = usage_ratios or {}
        self._scores = scores or {}

    def usage_ratio(self, org_id, usage_metric="alerts_sent", limit_metric="alerts_per_hour"):
        return self._usage_ratios.get(org_id)

    def score_organization(self, org: dict) -> int:
        return self._scores.get(org["_id"], 0)

    def predict_churn(self) -> list[dict]:
        return []


class FakeStripeSync:
    def __init__(self, upgrade_result=None, downgrade_result=None):
        self.upgrade_result = upgrade_result or {"status": "applied"}
        self.downgrade_result = downgrade_result or {"status": "applied"}
        self.upgrade_calls: list[tuple[str, str]] = []
        self.downgrade_calls: list[str] = []

    def upgrade_subscription(self, org_id: str, target_plan: str) -> dict:
        self.upgrade_calls.append((org_id, target_plan))
        return self.upgrade_result

    def downgrade_subscription(self, org_id: str) -> dict:
        self.downgrade_calls.append(org_id)
        return self.downgrade_result


def test_upgrade_org_stripe_bound_nao_altera_plano_direto():
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "free",
            "created_at": _days_ago(10),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    stripe_sync = FakeStripeSync(upgrade_result={"status": "pending", "checkout_url": "https://x"})
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=stripe_sync)

    applied = engine.run(execute=True)

    assert auth.plan_changes == []
    assert stripe_sync.upgrade_calls == [("org_1", "pro")]
    assert applied["upgrades"] == []
    assert applied["pending_checkout"] == [
        {
            "org_id": "org_1",
            "action": "upgrade",
            "checkout_url": "https://x",
            "reason": "requires_customer_action",
        }
    ]


def test_upgrade_org_stripe_bound_ativo_conta_como_aplicado():
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "free",
            "created_at": _days_ago(10),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    stripe_sync = FakeStripeSync(upgrade_result={"status": "applied"})
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=stripe_sync)

    applied = engine.run(execute=True)

    assert auth.plan_changes == []
    assert len(applied["upgrades"]) == 1
    assert applied["pending_checkout"] == []


def test_downgrade_org_stripe_bound_nunca_chama_stripe_sync():
    """Sprint 281: downgrade_subscription() used to be called for a
    Stripe-bound org here; as of this sprint, nothing ever calls it from
    BillingDecisionEngine -- self-serve billing (Sprint 280) is the
    customer's own exclusive path for this now. The candidate still
    surfaces as a recommendation, but purely as signal."""
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "pro",
            "created_at": _days_ago(40),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})
    stripe_sync = FakeStripeSync(downgrade_result={"status": "applied"})
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=stripe_sync)

    applied = engine.run(execute=True)

    assert auth.plan_changes == []
    assert stripe_sync.downgrade_calls == []
    assert len(applied["downgrade_recommendations"]) == 1
    assert applied["downgrade_recommendations"][0]["org_id"] == "org_1"
    assert orgs["org_1"]["plan"] == "pro"


def test_org_nao_stripe_bound_ainda_usa_mutacao_direta_mesmo_com_stripe_sync_configurado():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    stripe_sync = FakeStripeSync()
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=stripe_sync)

    applied = engine.run(execute=True)

    assert auth.plan_changes == [("org_1", "pro")]
    assert stripe_sync.upgrade_calls == []
    assert len(applied["upgrades"]) == 1


def test_org_stripe_bound_sem_stripe_sync_configurado_e_ignorada():
    """Sprint 278's hard safety floor, preserved: no stripe_sync
    available (Stripe not configured for this deployment) must never
    fall back to an unsafe direct plan mutation for a Stripe-bound org."""
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "free",
            "created_at": _days_ago(10),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=None)

    applied = engine.run(execute=True)

    assert auth.plan_changes == []
    assert applied["upgrades"] == []
    assert applied["pending_checkout"] == []
    assert orgs["org_1"]["plan"] == "free"


def test_proposta_dry_run_inclui_org_stripe_bound():
    """Sprint 279 removed Sprint 278's proposal-step exclusion of
    Stripe-bound orgs -- the routing decision now happens at execution
    time, not proposal time (see decision_engine.py's own module
    docstring), so the dry-run view should show it as a candidate."""
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "free",
            "created_at": _days_ago(10),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=None)

    proposal = engine.run()

    assert len(proposal["upgrades"]) == 1


def test_guardas_de_elegibilidade_ainda_se_aplicam_a_org_stripe_bound():
    """Eligibility criteria (tenure, score, usage) still gate whether a
    downgrade is even *recommended* -- a too-recent Stripe-bound org
    still shouldn't show up at all, regardless of Sprint 281's removal
    of downgrade execution."""
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "pro",
            "created_at": _days_ago(5),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})
    stripe_sync = FakeStripeSync()
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=stripe_sync)

    applied = engine.run(execute=True)

    assert applied["downgrade_recommendations"] == []
    assert stripe_sync.downgrade_calls == []
