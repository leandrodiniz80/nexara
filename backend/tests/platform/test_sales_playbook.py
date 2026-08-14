"""Tests for SalesPlaybookEngine (Sprint 284).

FakeActivationEngine gives full control over the underlying lead lists,
matching the established test-double pattern from
test_revenue_activation.py.
"""

from app.platform.revenue.sales_playbook import SalesPlaybookEngine


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


def test_generate_playbook_retorna_as_tres_chaves():
    engine = SalesPlaybookEngine(FakeActivationEngine())

    playbook = engine.generate_playbook()

    assert set(playbook.keys()) == {"high_intent", "churn_risk", "expansion"}


def test_playbook_vazio_quando_sem_leads():
    engine = SalesPlaybookEngine(FakeActivationEngine())

    playbook = engine.generate_playbook()

    assert playbook == {"high_intent": [], "churn_risk": [], "expansion": []}


# --- high_intent ---------------------------------------------------------


def test_high_intent_mensagem_personalizada_com_usage_ratio():
    activation = FakeActivationEngine(
        high_intent=[{"org_id": "org_1", "usage_ratio": 0.95, "score": 70}]
    )
    engine = SalesPlaybookEngine(activation)

    playbook = engine.generate_playbook()

    entry = playbook["high_intent"][0]
    assert entry["org_id"] == "org_1"
    assert "95%" in entry["message"]
    assert entry["action"] == "upgrade_offer"
    assert entry["priority"] == 70


def test_high_intent_arredonda_percentual_corretamente():
    activation = FakeActivationEngine(
        high_intent=[{"org_id": "org_1", "usage_ratio": 0.913, "score": 10}]
    )
    engine = SalesPlaybookEngine(activation)

    entry = engine.generate_playbook()["high_intent"][0]

    assert "91%" in entry["message"]


# --- churn_risk (the spec's own "for l in leads" bug) --------------------


def test_churn_playbook_gera_uma_entrada_por_lead():
    """Regression guard: the spec's own version referenced an undefined
    loop variable in a bare list literal (no `for l in leads` clause at
    all) -- would raise NameError immediately, and even patched
    naively could return only one entry regardless of how many leads
    existed. Confirms multiple leads all produce their own entries."""
    activation = FakeActivationEngine(
        churn_risk=[
            {"org_id": "org_1", "risk": "high", "reason": "payment_failed", "score": 50},
            {"org_id": "org_2", "risk": "high", "reason": "payment_failed", "score": 30},
        ]
    )
    engine = SalesPlaybookEngine(activation)

    entries = engine.generate_playbook()["churn_risk"]

    assert len(entries) == 2
    assert {e["org_id"] for e in entries} == {"org_1", "org_2"}


def test_churn_playbook_mensagem_e_action_corretos():
    activation = FakeActivationEngine(
        churn_risk=[{"org_id": "org_1", "risk": "high", "reason": "payment_failed", "score": 50}]
    )
    engine = SalesPlaybookEngine(activation)

    entry = engine.generate_playbook()["churn_risk"][0]

    assert entry["action"] == "retention_offer"
    assert "valor" in entry["message"]
    assert entry["priority"] == 50


# --- expansion (same "for l in leads" bug) --------------------------------


def test_expansion_playbook_gera_uma_entrada_por_lead():
    activation = FakeActivationEngine(
        expansion=[
            {
                "org_id": "org_1",
                "current_plan": "free",
                "recommended_plan": "pro",
                "reason": "high_usage",
                "score": 60,
            },
            {
                "org_id": "org_2",
                "current_plan": "free",
                "recommended_plan": "pro",
                "reason": "high_health",
                "score": 40,
            },
        ]
    )
    engine = SalesPlaybookEngine(activation)

    entries = engine.generate_playbook()["expansion"]

    assert len(entries) == 2
    assert {e["org_id"] for e in entries} == {"org_1", "org_2"}


def test_expansion_playbook_mensagem_e_action_corretos():
    activation = FakeActivationEngine(
        expansion=[
            {
                "org_id": "org_1",
                "current_plan": "free",
                "recommended_plan": "pro",
                "reason": "high_usage",
                "score": 60,
            }
        ]
    )
    engine = SalesPlaybookEngine(activation)

    entry = engine.generate_playbook()["expansion"][0]

    assert entry["action"] == "expansion_offer"
    assert "plano" in entry["message"]
    assert entry["priority"] == 60


# --- priority ordering ----------------------------------------------------


def test_ordenado_por_prioridade_decrescente():
    activation = FakeActivationEngine(
        high_intent=[
            {"org_id": "org_low", "usage_ratio": 0.95, "score": 10},
            {"org_id": "org_high", "usage_ratio": 0.95, "score": 90},
            {"org_id": "org_mid", "usage_ratio": 0.95, "score": 50},
        ]
    )
    engine = SalesPlaybookEngine(activation)

    entries = engine.generate_playbook()["high_intent"]

    assert [e["org_id"] for e in entries] == ["org_high", "org_mid", "org_low"]


def test_ordenacao_estavel_para_prioridades_iguais_nao_quebra():
    activation = FakeActivationEngine(
        churn_risk=[
            {"org_id": "org_a", "risk": "high", "reason": "payment_failed", "score": 20},
            {"org_id": "org_b", "risk": "high", "reason": "payment_failed", "score": 20},
        ]
    )
    engine = SalesPlaybookEngine(activation)

    entries = engine.generate_playbook()["churn_risk"]

    assert len(entries) == 2
    assert all(e["priority"] == 20 for e in entries)


# --- no mutation -----------------------------------------------------------


def test_nao_muta_leads_originais():
    high_intent = [{"org_id": "org_1", "usage_ratio": 0.95, "score": 70}]
    original = dict(high_intent[0])
    activation = FakeActivationEngine(high_intent=high_intent)
    engine = SalesPlaybookEngine(activation)

    engine.generate_playbook()

    assert high_intent[0] == original
