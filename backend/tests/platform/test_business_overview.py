"""Tests for BusinessOverviewEngine (Sprint 286, refined Sprint 287).

FakeAuth/FakeAnalytics/FakeActivationEngine/FakeLeadTracker give full
control over every underlying signal, matching the established
test-double pattern from test_revenue_activation.py onward. Sprint 287's
priority_score needs each org's real plan (for the revenue boost), so
FakeAnalytics now exposes `.auth` (a FakeAuth with `list_organizations()`)
the same way the real BillingAnalytics does.
"""

from app.platform.revenue.business_overview import BusinessOverviewEngine


class FakeAuth:
    def __init__(self, orgs: dict | None = None):
        self._orgs = orgs or {}

    def list_organizations(self) -> dict:
        return dict(self._orgs)


class FakeAnalytics:
    def __init__(
        self, mrr=0, active_customers=0, churn_rate=0.0, growth_rate=0.0, orgs=None
    ):
        self.auth = FakeAuth(orgs)
        self._mrr = mrr
        self._active_customers = active_customers
        self._churn_rate = churn_rate
        self._growth_rate = growth_rate

    def active_mrr(self) -> int:
        return self._mrr

    def active_customers(self) -> int:
        return self._active_customers

    def churn_rate(self) -> float:
        return self._churn_rate

    def growth_rate(self) -> float:
        return self._growth_rate


class FakeActivationEngine:
    def __init__(self, high_intent=None, churn_risk=None, expansion=None):
        self._high_intent = high_intent or []
        self._churn_risk = churn_risk or []
        self._expansion = expansion or []

    def high_intent_leads(self) -> list[dict]:
        return self._high_intent

    def churn_risk_leads(self) -> list[dict]:
        return self._churn_risk

    def expansion_opportunities(self) -> list[dict]:
        return self._expansion


class FakeLeadTracker:
    def __init__(self, summary=None):
        self._summary = summary or {}

    def conversion_summary(self) -> dict:
        return self._summary


def _lead(org_id: str, score: int, **extra) -> dict:
    return {"org_id": org_id, "score": score, **extra}


def _engine(analytics=None, activation=None, lead_tracker=None) -> BusinessOverviewEngine:
    return BusinessOverviewEngine(
        analytics or FakeAnalytics(),
        activation or FakeActivationEngine(),
        lead_tracker or FakeLeadTracker(),
    )


# --- generate_overview() structure -----------------------------------


def test_generate_overview_retorna_todas_as_chaves():
    overview = _engine().generate_overview()

    assert set(overview.keys()) == {
        "mrr",
        "active_customers",
        "churn_rate",
        "business_score",
        "business_status",
        "top_opportunities",
        "at_risk_customers",
        "top_customers",
        "conversion_summary",
        "weekly_focus",
        "executive_insight",
    }


def test_metricas_de_billing_vem_direto_do_analytics():
    analytics = FakeAnalytics(mrr=1188, active_customers=3, churn_rate=12.5)

    overview = _engine(analytics=analytics).generate_overview()

    assert overview["mrr"] == 1188
    assert overview["active_customers"] == 3
    assert overview["churn_rate"] == 12.5


def test_conversion_summary_repassado_sem_alteracao():
    summary = {"upgrade_offer": {"pending": 1, "conversion_rate": 0.5}}

    overview = _engine(lead_tracker=FakeLeadTracker(summary)).generate_overview()

    assert overview["conversion_summary"] == summary


# --- top_opportunities() ------------------------------------------------


def test_top_opportunities_combina_high_intent_e_expansion():
    activation = FakeActivationEngine(
        high_intent=[_lead("org_1", 50)],
        expansion=[_lead("org_2", 40)],
    )

    opportunities = _engine(activation=activation).top_opportunities()

    org_ids = {o["org_id"] for o in opportunities}
    assert org_ids == {"org_1", "org_2"}


def test_top_opportunities_marca_o_tipo_correto():
    activation = FakeActivationEngine(
        high_intent=[_lead("org_1", 50)],
        expansion=[_lead("org_2", 40)],
    )

    opportunities = {o["org_id"]: o for o in _engine(activation=activation).top_opportunities()}

    assert opportunities["org_1"]["type"] == "high_intent"
    assert opportunities["org_2"]["type"] == "expansion"


def test_top_opportunities_nao_deduplica_org_presente_nos_dois():
    """An org showing up in both high_intent and expansion is a real,
    meaningful signal -- both entries should be preserved."""
    activation = FakeActivationEngine(
        high_intent=[_lead("org_1", 70)],
        expansion=[_lead("org_1", 65)],
    )

    opportunities = _engine(activation=activation).top_opportunities()

    assert len(opportunities) == 2
    assert {o["type"] for o in opportunities} == {"high_intent", "expansion"}


def test_top_opportunities_ordenado_por_priority_score_decrescente():
    activation = FakeActivationEngine(
        high_intent=[_lead("org_low", 10), _lead("org_high", 90)],
    )

    opportunities = _engine(activation=activation).top_opportunities()

    assert [o["org_id"] for o in opportunities] == ["org_high", "org_low"]


def test_top_opportunities_respeita_limite():
    leads = [_lead(f"org_{i}", i) for i in range(15)]
    activation = FakeActivationEngine(high_intent=leads)

    opportunities = _engine(activation=activation).top_opportunities(limit=5)

    assert len(opportunities) == 5
    assert {o["org_id"] for o in opportunities} == {
        "org_14",
        "org_13",
        "org_12",
        "org_11",
        "org_10",
    }


def test_top_opportunities_preserva_campos_originais():
    activation = FakeActivationEngine(
        expansion=[_lead("org_1", 50, current_plan="free", recommended_plan="pro", reason="x")]
    )

    entry = _engine(activation=activation).top_opportunities()[0]

    assert entry["current_plan"] == "free"
    assert entry["recommended_plan"] == "pro"
    assert entry["reason"] == "x"


def test_top_opportunities_priority_score_ganha_boost_por_receita():
    orgs = {"org_1": {"plan": "enterprise"}}
    analytics = FakeAnalytics(orgs=orgs)
    activation = FakeActivationEngine(high_intent=[_lead("org_1", 10)])

    entry = _engine(analytics=analytics, activation=activation).top_opportunities()[0]

    # 10 (raw score) + 299/10 (enterprise plan price) = 39.9
    assert entry["priority_score"] == 39.9


def test_top_opportunities_sem_org_conhecida_nao_gera_boost():
    activation = FakeActivationEngine(high_intent=[_lead("org_unknown", 10)])

    entry = _engine(activation=activation).top_opportunities()[0]

    assert entry["priority_score"] == 10.0


# --- at_risk_customers() ------------------------------------------------


def test_at_risk_customers_vem_de_churn_risk_leads():
    activation = FakeActivationEngine(churn_risk=[_lead("org_1", 20, risk="high", reason="x")])

    customers = _engine(activation=activation).at_risk_customers()

    assert len(customers) == 1
    assert customers[0]["org_id"] == "org_1"
    assert customers[0]["type"] == "churn_risk"
    assert customers[0]["reason"] == "x"


def test_at_risk_customers_inclui_revenue_at_risk():
    orgs = {"org_1": {"plan": "pro"}}
    analytics = FakeAnalytics(orgs=orgs)
    activation = FakeActivationEngine(churn_risk=[_lead("org_1", 20, risk="high")])

    entry = _engine(analytics=analytics, activation=activation).at_risk_customers()[0]

    assert entry["revenue_at_risk"] == 99


def test_at_risk_customers_org_free_tem_revenue_at_risk_zero():
    activation = FakeActivationEngine(churn_risk=[_lead("org_1", 20, risk="high")])

    entry = _engine(activation=activation).at_risk_customers()[0]

    assert entry["revenue_at_risk"] == 0


def test_at_risk_customers_nao_e_limitado():
    leads = [_lead(f"org_{i}", i, risk="high") for i in range(20)]
    activation = FakeActivationEngine(churn_risk=leads)

    customers = _engine(activation=activation).at_risk_customers()

    assert len(customers) == 20


def test_at_risk_customers_ordenado_por_priority_score_decrescente():
    activation = FakeActivationEngine(
        churn_risk=[_lead("org_low", 5, risk="high"), _lead("org_high", 55, risk="high")]
    )

    customers = _engine(activation=activation).at_risk_customers()

    assert [c["org_id"] for c in customers] == ["org_high", "org_low"]


# --- top_customers() ------------------------------------------------------


def test_top_customers_ranqueia_por_receita():
    orgs = {
        "org_free": {"plan": "free"},
        "org_pro": {"plan": "pro"},
        "org_enterprise": {"plan": "enterprise"},
    }
    analytics = FakeAnalytics(orgs=orgs)

    customers = _engine(analytics=analytics).top_customers()

    assert [c["org_id"] for c in customers] == ["org_enterprise", "org_pro"]
    assert customers[0]["revenue"] == 299
    assert customers[1]["revenue"] == 99


def test_top_customers_exclui_organizacoes_free():
    orgs = {"org_free": {"plan": "free"}}
    analytics = FakeAnalytics(orgs=orgs)

    customers = _engine(analytics=analytics).top_customers()

    assert customers == []


def test_top_customers_respeita_limite():
    orgs = {f"org_{i}": {"plan": "pro"} for i in range(15)}
    analytics = FakeAnalytics(orgs=orgs)

    customers = _engine(analytics=analytics).top_customers(limit=5)

    assert len(customers) == 5


def test_top_customers_nao_tem_priority_score():
    orgs = {"org_1": {"plan": "pro"}}
    analytics = FakeAnalytics(orgs=orgs)

    entry = _engine(analytics=analytics).top_customers()[0]

    assert "priority_score" not in entry
    assert "recommended_action" not in entry


# --- priority_score / recommended_action -----------------------------


def test_score_alto_recomenda_contact_now():
    activation = FakeActivationEngine(high_intent=[_lead("org_1", 60)])

    entry = _engine(activation=activation).top_opportunities()[0]

    assert entry["priority_score"] == 60.0
    assert entry["recommended_action"] == "contact_now"


def test_score_medio_recomenda_monitor():
    activation = FakeActivationEngine(high_intent=[_lead("org_1", 30)])

    entry = _engine(activation=activation).top_opportunities()[0]

    assert entry["recommended_action"] == "monitor"


def test_score_baixo_recomenda_ignore():
    activation = FakeActivationEngine(high_intent=[_lead("org_1", 10)])

    entry = _engine(activation=activation).top_opportunities()[0]

    assert entry["recommended_action"] == "ignore"


def test_score_negativo_recomenda_ignore():
    activation = FakeActivationEngine(churn_risk=[_lead("org_1", -30, risk="high")])

    entry = _engine(activation=activation).at_risk_customers()[0]

    assert entry["priority_score"] == -30.0
    assert entry["recommended_action"] == "ignore"


def test_limiares_sao_inclusive_no_limite_inferior():
    activation = FakeActivationEngine(
        high_intent=[_lead("org_high", 60), _lead("org_med", 30), _lead("org_low", 29)]
    )

    by_id = {e["org_id"]: e for e in _engine(activation=activation).top_opportunities()}

    assert by_id["org_high"]["recommended_action"] == "contact_now"
    assert by_id["org_med"]["recommended_action"] == "monitor"
    assert by_id["org_low"]["recommended_action"] == "ignore"


def test_priority_nao_existe_mais_no_payload():
    """Sprint 287's own explicit "replace priority with priority_score"."""
    activation = FakeActivationEngine(high_intent=[_lead("org_1", 60)])

    entry = _engine(activation=activation).top_opportunities()[0]

    assert "priority" not in entry


# --- business_score() / business_status() ---------------------------------


def test_business_score_baseline_sem_nenhum_sinal():
    score = _engine().business_score()

    assert score == 50


def test_business_score_sobe_com_crescimento():
    analytics = FakeAnalytics(growth_rate=20.0)

    score = _engine(analytics=analytics).business_score()

    assert score == 70


def test_business_score_crescimento_e_limitado_a_25():
    analytics = FakeAnalytics(growth_rate=1000.0)

    score = _engine(analytics=analytics).business_score()

    assert score == 75


def test_business_score_desce_com_churn():
    analytics = FakeAnalytics(churn_rate=20.0)

    score = _engine(analytics=analytics).business_score()

    assert score == 30


def test_business_score_churn_e_limitado_a_25():
    analytics = FakeAnalytics(churn_rate=1000.0)

    score = _engine(analytics=analytics).business_score()

    assert score == 25


def test_business_score_sobe_com_conversao():
    lead_tracker = FakeLeadTracker({"upgrade_offer": {"conversion_rate": 1.0}})

    score = _engine(lead_tracker=lead_tracker).business_score()

    assert score == 70


def test_business_score_desce_com_risco_de_churn():
    analytics = FakeAnalytics(active_customers=2)
    activation = FakeActivationEngine(
        churn_risk=[_lead("org_1", 0, risk="high"), _lead("org_2", 0, risk="high")]
    )

    score = _engine(analytics=analytics, activation=activation).business_score()

    assert score == 25


def test_business_score_fica_entre_0_e_100():
    analytics = FakeAnalytics(growth_rate=-1000.0, churn_rate=1000.0)

    score = _engine(analytics=analytics).business_score()

    assert 0 <= score <= 100


def test_business_status_growing():
    engine = _engine()

    assert engine.business_status(70) == "growing"
    assert engine.business_status(100) == "growing"


def test_business_status_stable():
    engine = _engine()

    assert engine.business_status(40) == "stable"
    assert engine.business_status(69) == "stable"


def test_business_status_risk():
    engine = _engine()

    assert engine.business_status(0) == "risk"
    assert engine.business_status(39) == "risk"


# --- weekly_focus() ------------------------------------------------------


def test_weekly_focus_sem_candidatos_retorna_mensagem_padrao():
    focus = _engine().weekly_focus()

    assert focus["org_id"] is None
    assert "message" in focus


def test_weekly_focus_seleciona_maior_priority_score():
    activation = FakeActivationEngine(
        high_intent=[_lead("org_low", 10)],
        churn_risk=[_lead("org_high", 80, risk="high", reason="payment_failed")],
    )

    focus = _engine(activation=activation).weekly_focus()

    assert focus["org_id"] == "org_high"
    assert focus["type"] == "churn_risk"
    assert focus["recommended_action"] == "contact_now"
    assert "org_high" in focus["message"]


# --- executive_insight() --------------------------------------------------


def test_executive_insight_e_uma_string_nao_vazia():
    insight = _engine().executive_insight(50, "stable")

    assert isinstance(insight, str)
    assert len(insight) > 0


def test_executive_insight_menciona_o_score_e_status():
    insight = _engine().executive_insight(72, "growing")

    assert "72" in insight
    assert "growing" in insight.lower()


# --- no side effects / no new intelligence --------------------------------


def test_business_overview_nao_muta_leads_originais():
    high_intent = [_lead("org_1", 50)]
    original = dict(high_intent[0])
    activation = FakeActivationEngine(high_intent=high_intent)

    _engine(activation=activation).generate_overview()

    assert high_intent[0] == original
