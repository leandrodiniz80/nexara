"""Tests for RevenueActivationEngine (Sprint 283).

FakeAnalytics gives full control over usage/health/churn/upgrade-rec
inputs, matching the established test-double pattern from
test_decision_engine.py onward -- `_id`-keyed score lookups are a
test-only convention, not something the real BillingAnalytics.
score_organization() reads.
"""

from app.platform.revenue.revenue_activation import RevenueActivationEngine


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return dict(self._orgs)


class FakeAnalytics:
    def __init__(
        self, auth, usage_ratios=None, scores=None, churn=None, upgrade_recs=None
    ):
        self.auth = auth
        self._usage_ratios = usage_ratios or {}
        self._scores = scores or {}
        self._churn = churn or []
        self._upgrade_recs = upgrade_recs or []

    def usage_ratio(self, org_id, usage_metric="alerts_sent", limit_metric="alerts_per_hour"):
        return self._usage_ratios.get(org_id)

    def score_organization(self, org: dict) -> int:
        return self._scores.get(org.get("_id"), 0)

    def predict_churn(self) -> list[dict]:
        return self._churn

    def upgrade_recommendations(self) -> list[dict]:
        return self._upgrade_recs


# --- score_lead() ------------------------------------------------------


def test_score_lead_soma_todos_os_fatores_positivos():
    auth = FakeAuth({})
    analytics = FakeAnalytics(
        auth, usage_ratios={"org_1": 0.9}, scores={"org_1": 60}
    )
    engine = RevenueActivationEngine(analytics)
    org = {"_id": "org_1", "plan": "pro"}

    score = engine.score_lead("org_1", org, churn_risk=None)

    assert score == 40 + 30 + 20


def test_score_lead_aplica_penalidade_de_churn_alto():
    auth = FakeAuth({})
    analytics = FakeAnalytics(auth, usage_ratios={}, scores={"org_1": 0})
    engine = RevenueActivationEngine(analytics)
    org = {"_id": "org_1", "plan": "free"}

    score = engine.score_lead("org_1", org, churn_risk="high")

    assert score == -30


def test_score_lead_nao_penaliza_churn_medio_ou_baixo():
    auth = FakeAuth({})
    analytics = FakeAnalytics(auth, usage_ratios={}, scores={"org_1": 0})
    engine = RevenueActivationEngine(analytics)
    org = {"_id": "org_1", "plan": "free"}

    assert engine.score_lead("org_1", org, churn_risk="medium") == 0
    assert engine.score_lead("org_1", org, churn_risk="low") == 0


def test_score_lead_sem_sinal_de_uso_nao_soma_nem_quebra():
    auth = FakeAuth({})
    analytics = FakeAnalytics(auth, usage_ratios={}, scores={"org_1": 0})
    engine = RevenueActivationEngine(analytics)
    org = {"_id": "org_1", "plan": "free"}

    assert engine.score_lead("org_1", org) == 0


# --- high_intent_leads() ------------------------------------------------


def test_high_intent_inclui_organizacao_elegivel():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(auth, usage_ratios={"org_1": 0.95}, scores={"org_1": 60})
    engine = RevenueActivationEngine(analytics)

    leads = engine.high_intent_leads()

    assert len(leads) == 1
    assert leads[0]["org_id"] == "org_1"
    assert leads[0]["plan"] == "pro"
    assert leads[0]["usage_ratio"] == 0.95
    assert leads[0]["health_score"] == 60
    assert "score" in leads[0]


def test_high_intent_exclui_plano_enterprise():
    orgs = {"org_1": {"_id": "org_1", "plan": "enterprise"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(auth, usage_ratios={"org_1": 0.99}, scores={"org_1": 90})
    engine = RevenueActivationEngine(analytics)

    assert engine.high_intent_leads() == []


def test_high_intent_exclui_uso_baixo():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(auth, usage_ratios={"org_1": 0.5}, scores={"org_1": 60})
    engine = RevenueActivationEngine(analytics)

    assert engine.high_intent_leads() == []


def test_high_intent_exclui_health_score_baixo():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(auth, usage_ratios={"org_1": 0.95}, scores={"org_1": 40})
    engine = RevenueActivationEngine(analytics)

    assert engine.high_intent_leads() == []


def test_high_intent_exclui_sem_sinal_de_uso():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(auth, usage_ratios={}, scores={"org_1": 60})
    engine = RevenueActivationEngine(analytics)

    assert engine.high_intent_leads() == []


def test_high_intent_ordenado_por_score_decrescente():
    orgs = {
        "org_low": {"_id": "org_low", "plan": "free"},
        "org_high": {"_id": "org_high", "plan": "pro"},
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        auth,
        usage_ratios={"org_low": 0.95, "org_high": 0.95},
        scores={"org_low": 51, "org_high": 90},
    )
    engine = RevenueActivationEngine(analytics)

    leads = engine.high_intent_leads()

    assert [lead["org_id"] for lead in leads] == ["org_high", "org_low"]
    assert leads[0]["score"] >= leads[1]["score"]


# --- churn_risk_leads() -------------------------------------------------


def test_churn_risk_inclui_apenas_risco_alto():
    auth = FakeAuth({"org_1": {"_id": "org_1", "plan": "pro"}, "org_2": {"_id": "org_2"}})
    analytics = FakeAnalytics(
        auth,
        churn=[
            {"org_id": "org_1", "risk": "high", "reason": "payment_failed"},
            {"org_id": "org_2", "risk": "medium", "reason": "low_health"},
        ],
    )
    engine = RevenueActivationEngine(analytics)

    leads = engine.churn_risk_leads()

    assert len(leads) == 1
    assert leads[0]["org_id"] == "org_1"
    assert leads[0]["risk"] == "high"
    assert leads[0]["reason"] == "payment_failed"
    assert "score" in leads[0]


def test_churn_risk_ordenado_por_score_decrescente():
    orgs = {
        "org_a": {"_id": "org_a", "plan": "free"},
        "org_b": {"_id": "org_b", "plan": "pro"},
    }
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        auth,
        scores={"org_a": 0, "org_b": 0},
        churn=[
            {"org_id": "org_a", "risk": "high", "reason": "payment_failed"},
            {"org_id": "org_b", "risk": "high", "reason": "payment_failed"},
        ],
    )
    engine = RevenueActivationEngine(analytics)

    leads = engine.churn_risk_leads()

    assert leads[0]["org_id"] == "org_b"
    assert leads[0]["score"] >= leads[1]["score"]


# --- expansion_opportunities() -------------------------------------------


def test_expansion_reutiliza_upgrade_recommendations():
    auth = FakeAuth({"org_1": {"_id": "org_1", "plan": "free"}})
    upgrade_recs = [
        {
            "org_id": "org_1",
            "current_plan": "free",
            "recommended_plan": "pro",
            "reason": "high_usage",
        }
    ]
    analytics = FakeAnalytics(auth, scores={"org_1": 0}, upgrade_recs=upgrade_recs)
    engine = RevenueActivationEngine(analytics)

    leads = engine.expansion_opportunities()

    assert len(leads) == 1
    assert leads[0]["org_id"] == "org_1"
    assert leads[0]["current_plan"] == "free"
    assert leads[0]["recommended_plan"] == "pro"
    assert leads[0]["reason"] == "high_usage"
    assert "score" in leads[0]


def test_expansion_vazio_quando_sem_recomendacoes():
    auth = FakeAuth({})
    analytics = FakeAnalytics(auth)
    engine = RevenueActivationEngine(analytics)

    assert engine.expansion_opportunities() == []


# --- no side effects -----------------------------------------------------


def test_sem_efeito_colateral():
    orgs = {"org_1": {"_id": "org_1", "plan": "pro"}}
    auth = FakeAuth(orgs)
    analytics = FakeAnalytics(
        auth,
        usage_ratios={"org_1": 0.95},
        scores={"org_1": 60},
        churn=[{"org_id": "org_1", "risk": "high", "reason": "payment_failed"}],
        upgrade_recs=[
            {
                "org_id": "org_1",
                "current_plan": "pro",
                "recommended_plan": "enterprise",
                "reason": "high_usage",
            }
        ],
    )
    engine = RevenueActivationEngine(analytics)

    engine.high_intent_leads()
    engine.churn_risk_leads()
    engine.expansion_opportunities()

    assert orgs == {"org_1": {"_id": "org_1", "plan": "pro"}}
