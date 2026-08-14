"""Tests for BillingDecisionEngine's Sprint 281 downgrade-never-executes
behavior: self-serve billing (Sprint 280, the Stripe Customer Portal)
made downgrade/cancellation the customer's own exclusive responsibility,
so BillingDecisionEngine now only ever *recommends* a downgrade, never
applies one.
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


def _eligible_org():
    return {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(40)}}


def _eligible_analytics():
    return FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})


def test_downgrade_nunca_executa_via_apply_plan_change():
    """Direct unit test of the defensive guard: even if _apply_plan_
    change() were somehow called with a downgrade action, it refuses to
    mutate anything and reports why."""
    auth = FakeAuth(_eligible_org())
    analytics = _eligible_analytics()
    engine = BillingDecisionEngine(analytics, auth)
    action = {
        "org_id": "org_1",
        "action": "downgrade",
        "from": "pro",
        "to": "free",
        "reason": "low_engagement",
    }

    result = engine._apply_plan_change(action)

    assert result == {"status": "skipped", "reason": "self_serve_billing_enabled"}
    assert auth.plan_changes == []


def test_downgrade_nunca_executa_via_run():
    orgs = _eligible_org()
    auth = FakeAuth(orgs)
    analytics = _eligible_analytics()
    engine = BillingDecisionEngine(analytics, auth)

    engine.run(execute=True)

    assert auth.plan_changes == []
    assert orgs["org_1"]["plan"] == "pro"


def test_downgrade_aparece_em_downgrade_recommendations_no_dry_run():
    auth = FakeAuth(_eligible_org())
    analytics = _eligible_analytics()
    engine = BillingDecisionEngine(analytics, auth)

    proposal = engine.run()

    assert len(proposal["downgrade_recommendations"]) == 1
    assert proposal["downgrade_recommendations"][0]["org_id"] == "org_1"
    assert proposal["downgrade_recommendations"][0]["action"] == "downgrade"


def test_downgrade_aparece_em_downgrade_recommendations_ao_executar():
    auth = FakeAuth(_eligible_org())
    analytics = _eligible_analytics()
    engine = BillingDecisionEngine(analytics, auth)

    applied = engine.run(execute=True)

    assert len(applied["downgrade_recommendations"]) == 1
    assert applied["downgrade_recommendations"][0]["org_id"] == "org_1"


def test_downgrade_recommendations_identico_entre_dry_run_e_execute():
    auth = FakeAuth(_eligible_org())
    analytics = _eligible_analytics()
    engine = BillingDecisionEngine(analytics, auth)

    dry_run = engine.run()
    executed = engine.run(execute=True)

    assert dry_run["downgrade_recommendations"] == executed["downgrade_recommendations"]


def test_downgrade_nunca_executa_mesmo_para_org_stripe_bound_com_sync_configurado():
    """The Sprint 279 Stripe-routing machinery still exists for upgrades
    -- confirms it is never reached for downgrades, Stripe-bound or
    not."""
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "pro",
            "created_at": _days_ago(40),
            "stripe_subscription_id": "sub_1",
        }
    }
    auth = FakeAuth(orgs)
    analytics = _eligible_analytics()

    class FakeStripeSync:
        def __init__(self):
            self.downgrade_calls = []

        def downgrade_subscription(self, org_id):
            self.downgrade_calls.append(org_id)
            return {"status": "applied"}

    stripe_sync = FakeStripeSync()
    engine = BillingDecisionEngine(analytics, auth, stripe_sync=stripe_sync)

    engine.run(execute=True)

    assert stripe_sync.downgrade_calls == []
    assert orgs["org_1"]["plan"] == "pro"


def test_downgrade_nao_e_auditavel_como_billing_auto_action():
    """No plan mutation occurred, so nothing here should look like an
    executed action from the caller's side -- confirmed indirectly:
    run(execute=True) never calls set_organization_plan for a downgrade
    candidate, which is what a router's audit loop keys off of."""
    orgs = _eligible_org()
    auth = FakeAuth(orgs)
    analytics = _eligible_analytics()
    engine = BillingDecisionEngine(analytics, auth)

    applied = engine.run(execute=True)

    assert applied["upgrades"] == []
    assert applied["retention"] == []
    assert auth.plan_changes == []
