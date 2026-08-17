"""Tests for BillingDecisionEngine (Sprint 278).

FakeAuth/FakeAnalytics give full control over score/usage/churn inputs
so BillingDecisionEngine's own rule logic (tenure gates, Stripe guards,
dry-run vs execute) can be tested in isolation from BillingAnalytics's
specific scoring formula -- important here because, as
decision_engine.py's own module docstring and the tests at the bottom
of this file document, the *real* BillingAnalytics.score_organization()
can never actually satisfy auto_downgrade()'s "score < 40" condition or
auto_upgrade()'s "score > 85" condition for the org types each method
considers, given Sprint 276's fixed scoring weights.

Sprint 281 note: downgrade proposals now live under
"downgrade_recommendations" (renamed from "downgrades") and are never
executed by anything, `execute=True` or not -- see
decision_engine.py's own module docstring. Tests below were updated
accordingly; see test_decision_engine_no_downgrade.py for the dedicated
Sprint 281 coverage.
"""

import time

from app.platform.auth.platform_auth import PlatformAuth
from app.platform.billing.billing_analytics import BillingAnalytics
from app.platform.billing.decision_engine import BillingDecisionEngine

_DAY = 86400


def _days_ago(n: int) -> int:
    return int(time.time()) - n * _DAY


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs
        self.plan_changes: list[tuple[str, str]] = []
        self.retention_flags: list[tuple[str, bool]] = []

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
        org = self._orgs.get(org_id)
        if org is None:
            raise LookupError(org_id)
        org["retention_flag"] = flag
        self.retention_flags.append((org_id, flag))


class FakeAnalytics:
    def __init__(self, usage_ratios: dict | None = None, scores: dict | None = None, churn=None):
        self._usage_ratios = usage_ratios or {}
        self._scores = scores or {}
        self._churn = churn or []

    def usage_ratio(self, org_id, usage_metric="alerts_sent", limit_metric="alerts_per_hour"):
        return self._usage_ratios.get(org_id)

    def score_organization(self, org: dict) -> int:
        return self._scores.get(org["_id"], 0)

    def predict_churn(self) -> list[dict]:
        return self._churn


# --- auto_upgrade / dry-run vs execute -----------------------------------


def test_dry_run_nao_muta_nada():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth)

    proposal = engine.run()

    assert proposal["upgrades"] == [
        {
            "org_id": "org_1",
            "action": "upgrade",
            "from": "free",
            "to": "pro",
            "reason": "over_usage",
        }
    ]
    assert auth.plan_changes == []
    assert orgs["org_1"]["plan"] == "free"


def test_upgrade_acontece_ao_executar():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth)

    applied = engine.run(execute=True)

    assert applied["upgrades"] == [
        {
            "org_id": "org_1",
            "action": "upgrade",
            "from": "free",
            "to": "pro",
            "reason": "over_usage",
        }
    ]
    assert auth.plan_changes == [("org_1", "pro")]
    assert orgs["org_1"]["plan"] == "pro"


def test_upgrade_por_saude_alta():
    orgs = {"org_1": {"_id": "org_1", "plan": "free"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={}, scores={"org_1": 90})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["upgrades"][0]["reason"] == "high_health"


def test_sem_upgrade_abaixo_dos_limiares():
    orgs = {"org_1": {"_id": "org_1", "plan": "free"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.5}, scores={"org_1": 60})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["upgrades"] == []


def test_upgrade_ignora_plano_ja_pago():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 5.0}, scores={"org_1": 100})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["upgrades"] == []


def test_upgrade_org_vinculada_ao_stripe_nao_muta_plano_direto_sem_stripe_sync():
    """Sprint 279 note: Sprint 278's original version of this test
    asserted the proposal itself excluded a Stripe-bound org entirely.
    That exclusion moved from the proposal step to the execution step
    this sprint (see decision_engine.py's own module docstring and
    test_decision_engine_stripe_safe.py for the full Sprint 279 routing
    behavior) — a Stripe-bound org is now proposed, but with no
    `stripe_sync` configured (this engine's default), executing it is
    still safely skipped rather than mutating `plan` directly, which is
    the one guarantee that must never regress."""
    orgs = {
        "org_1": {
            "_id": "org_1",
            "plan": "free",
            "stripe_subscription_id": "sub_123",
        }
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 5.0}, scores={"org_1": 100})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run(execute=True)["upgrades"] == []
    assert engine.run(execute=True)["pending_checkout"] == []
    assert orgs["org_1"]["plan"] == "free"


# --- auto_retention --------------------------------------------------------


def test_retention_flag_marca_risco_alto():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        churn=[{"org_id": "org_1", "risk": "high", "reason": "payment_failed"}]
    )
    engine = BillingDecisionEngine(analytics, auth)

    proposal = engine.run()
    assert proposal["retention"] == [
        {"org_id": "org_1", "action": "retention_flag", "reason": "payment_failed"}
    ]
    assert auth.retention_flags == []

    applied = engine.run(execute=True)
    assert applied["retention"] == proposal["retention"]
    assert auth.retention_flags == [("org_1", True)]
    assert orgs["org_1"]["retention_flag"] is True


def test_retention_ignora_risco_medio_e_baixo():
    orgs = {"org_1": {"_id": "org_1"}, "org_2": {"_id": "org_2"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        churn=[
            {"org_id": "org_1", "risk": "medium", "reason": "low_health"},
            {"org_id": "org_2", "risk": "low", "reason": "healthy"},
        ]
    )
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["retention"] == []


# --- auto_downgrade (recommendation-only as of Sprint 281) ---------------


def test_downgrade_elegivel_aparece_como_recomendacao_mas_nunca_executa():
    """Sprint 281: downgrades are never applied by anything, execute=True
    or not -- self-serve billing (Sprint 280) is the customer's own
    exclusive path now. Full dedicated coverage in
    test_decision_engine_no_downgrade.py; kept here alongside the
    equivalent upgrade test above for symmetry."""
    orgs = {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(40)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})
    engine = BillingDecisionEngine(analytics, auth)

    proposal = engine.run()
    assert proposal["downgrade_recommendations"] == [
        {
            "org_id": "org_1",
            "action": "downgrade",
            "from": "pro",
            "to": "free",
            "reason": "low_engagement",
        }
    ]

    applied = engine.run(execute=True)
    assert applied["downgrade_recommendations"] == proposal["downgrade_recommendations"]
    assert auth.plan_changes == []
    assert orgs["org_1"]["plan"] == "pro"


def test_downgrade_bloqueado_org_recente():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(5)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["downgrade_recommendations"] == []


def test_downgrade_bloqueado_sem_created_at():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.05}, scores={"org_1": 20})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["downgrade_recommendations"] == []


def test_downgrade_recomendado_para_org_vinculada_ao_stripe_tambem_nunca_executa():
    """Sprint 281 note: this test previously covered the Sprint 279
    "no stripe_sync configured" case specifically; as of this sprint
    that distinction is moot for downgrades -- Stripe-bound or not,
    nothing ever executes one. Kept as an explicit regression guard."""
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
    engine = BillingDecisionEngine(analytics, auth)

    applied = engine.run(execute=True)
    assert len(applied["downgrade_recommendations"]) == 1
    assert orgs["org_1"]["plan"] == "pro"


def test_downgrade_bloqueado_uso_nao_baixo_o_suficiente():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(40)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.5}, scores={"org_1": 20})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["downgrade_recommendations"] == []


def test_downgrade_bloqueado_sem_sinal_de_uso():
    """No usage source configured -> usage_ratio() is None -> "can't
    confirm low usage" is treated conservatively as "don't recommend",
    not as "assume worst-case low usage"."""
    orgs = {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(40)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={}, scores={"org_1": 20})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["downgrade_recommendations"] == []


def test_downgrade_bloqueado_score_nao_baixo_o_suficiente():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro", "created_at": _days_ago(40)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 0.01}, scores={"org_1": 60})
    engine = BillingDecisionEngine(analytics, auth)

    assert engine.run()["downgrade_recommendations"] == []


# --- filters (org_id / action_type) ----------------------------------------


def test_filtro_por_org_id():
    orgs = {
        "org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)},
        "org_2": {"_id": "org_2", "plan": "free", "created_at": _days_ago(10)},
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        usage_ratios={"org_1": 1.5, "org_2": 1.5}, scores={"org_1": 0, "org_2": 0}
    )
    engine = BillingDecisionEngine(analytics, auth)

    proposal = engine.run(org_id="org_1")

    assert [a["org_id"] for a in proposal["upgrades"]] == ["org_1"]


def test_filtro_por_action_type():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        usage_ratios={"org_1": 1.5},
        scores={"org_1": 0},
        churn=[{"org_id": "org_1", "risk": "high", "reason": "payment_failed"}],
    )
    engine = BillingDecisionEngine(analytics, auth)

    proposal = engine.run(action_type="retention_flag")

    assert proposal["upgrades"] == []
    assert len(proposal["retention"]) == 1


def test_execute_so_aplica_acoes_filtradas():
    orgs = {
        "org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)},
        "org_2": {"_id": "org_2", "plan": "free", "created_at": _days_ago(10)},
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        usage_ratios={"org_1": 1.5, "org_2": 1.5}, scores={"org_1": 0, "org_2": 0}
    )
    engine = BillingDecisionEngine(analytics, auth)

    engine.run(execute=True, org_id="org_1")

    assert orgs["org_1"]["plan"] == "pro"
    assert orgs["org_2"]["plan"] == "free"


# --- bug #1: validate org still exists / hasn't drifted ------------------


def test_apply_ignora_org_removida_entre_proposta_e_execucao():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth)

    del orgs["org_1"]

    applied = engine.run(execute=True)

    assert applied["upgrades"] == []
    assert auth.plan_changes == []


def test_apply_ignora_org_cujo_plano_mudou_entre_proposta_e_execucao():
    orgs = {"org_1": {"_id": "org_1", "plan": "free", "created_at": _days_ago(10)}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(usage_ratios={"org_1": 1.5}, scores={"org_1": 0})
    engine = BillingDecisionEngine(analytics, auth)

    orgs["org_1"]["plan"] = "pro"

    applied = engine.run(execute=True)

    assert applied["upgrades"] == []
    assert auth.plan_changes == []


# --- reachability of the score-based conditions under real weights -------


def test_auto_upgrade_criterio_de_saude_e_estruturalmente_inalcancavel_no_mundo_real():
    """A free-plan org's real score_organization() is capped at 60 (30
    active + 20 no-failure + 10 tenure -- the +40 for a paid plan is
    unreachable by definition for an org this method only considers
    when plan == "free"), never above the 85 auto_upgrade() checks
    against for the "high_health" branch. Documents the limitation
    rather than silently inventing a different threshold -- see
    auto_upgrade()'s own docstring."""
    real_auth = PlatformAuth()
    org_id = real_auth.create_organization("Acme")
    real_auth.set_organization_created_at(org_id, _days_ago(60))
    real_analytics = BillingAnalytics(real_auth, get_usage=None)

    org = real_auth.get_organization(org_id)
    assert real_analytics.score_organization(org) == 60

    engine = BillingDecisionEngine(real_analytics, real_auth)
    assert engine.run()["upgrades"] == []


def test_auto_downgrade_criterio_de_saude_e_estruturalmente_inalcancavel_no_mundo_real():
    """Every paid-plan org's real score_organization() has a floor of 60
    (the +40 for any non-free plan, plus at least +20 from the
    canceled/past_due pair -- subscription_status can only ever lose
    ONE of the +30/+20, never both, since it's a single field) --
    never below the 40 auto_downgrade() checks against. This makes
    auto_downgrade() permanently return [] under Sprint 276's fixed
    scoring weights, regardless of tenure or usage. See
    auto_downgrade()'s own docstring and decision_engine.py's module
    docstring."""
    real_auth = PlatformAuth()
    org_id = real_auth.create_organization("Acme")
    real_auth.set_organization_plan(org_id, "pro")
    real_auth.set_subscription_status(org_id, "canceled")
    real_auth.set_organization_created_at(org_id, _days_ago(60))
    real_analytics = BillingAnalytics(real_auth, get_usage=lambda org_id, metric: 0)

    org = real_auth.get_organization(org_id)
    assert real_analytics.score_organization(org) == 60

    engine = BillingDecisionEngine(real_analytics, real_auth)
    assert engine.run()["downgrade_recommendations"] == []
