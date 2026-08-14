"""Tests for BillingAnalytics.upgrade_recommendations() (Sprint 277).

FakeAuth.get_usage_limit() stands in for PlatformAuth.get_usage_limit()
(Sprint 270); the `get_usage` callable stands in for
LoaderMetricsStore.get_usage() (Sprint 270), injected the same way
UsageAlerts (Sprint 271) takes its callables — see
BillingAnalytics.__init__'s own docstring.
"""

import time

from app.platform.billing.billing_analytics import BillingAnalytics


class FakeAuth:
    def __init__(self, orgs: dict, limits: dict | None = None):
        self._orgs = orgs
        self._limits = limits or {}

    def list_organizations(self) -> dict:
        return self._orgs

    def get_usage_limit(self, org_id: str, metric: str) -> int:
        return self._limits.get(org_id, 50)


def test_free_com_uso_alto_e_recomendado():
    auth = FakeAuth({"org_1": {"plan": "free"}})
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: 45)

    result = analytics.upgrade_recommendations()

    assert result == [
        {
            "org_id": "org_1",
            "current_plan": "free",
            "recommended_plan": "pro",
            "reason": "high_usage",
        }
    ]


def test_free_com_uso_abaixo_de_80_por_cento_nao_e_recomendado():
    auth = FakeAuth({"org_1": {"plan": "free"}})
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: 10)

    assert analytics.upgrade_recommendations() == []


def test_exatos_80_por_cento_e_recomendado():
    auth = FakeAuth({"org_1": {"plan": "free"}}, limits={"org_1": 50})
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: 40)

    result = analytics.upgrade_recommendations()

    assert len(result) == 1
    assert result[0]["reason"] == "high_usage"


def test_plano_pago_nunca_e_recomendado_mesmo_com_uso_alto():
    auth = FakeAuth({"org_1": {"plan": "pro"}})
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: 999)

    assert analytics.upgrade_recommendations() == []


def test_sem_get_usage_configurado_nao_gera_erro():
    """No usage source wired (get_usage=None, the default) -> high_usage
    can never be True, but nothing crashes."""
    auth = FakeAuth({"org_1": {"plan": "free"}})
    analytics = BillingAnalytics(auth)

    assert analytics.upgrade_recommendations() == []


def test_limite_zero_ou_ausente_nao_gera_erro_de_divisao():
    auth = FakeAuth({"org_1": {"plan": "free"}}, limits={"org_1": 0})
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: 5)

    assert analytics.upgrade_recommendations() == []


def test_limite_ilimitado_nao_gera_recomendacao_por_uso():
    auth = FakeAuth({"org_1": {"plan": "free"}}, limits={"org_1": -1})
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: 999)

    assert analytics.upgrade_recommendations() == []


def test_score_alto_e_estruturalmente_inalcancavel_para_org_free():
    """_score_organization() awards the paid-plan +40 only to
    plan != "free" orgs -- since this method only ever evaluates orgs
    that already passed its own plan == "free" filter, the maximum score
    any candidate can reach is 60 (30 active + 20 no-failure + 10
    tenure), never > 80. This documents that the spec's "score > 80"
    criterion is dead code under the fixed Sprint 276 scoring weights,
    per upgrade_recommendations()'s own docstring -- not silently
    dropped, but not invented a new threshold for either."""
    auth = FakeAuth({"org_1": {"plan": "free", "subscription_status": "active"}})
    org = auth.list_organizations()["org_1"]
    org["created_at"] = int(time.time()) - 40 * 86400

    analytics = BillingAnalytics(auth)

    assert analytics._score_organization(org, int(time.time())) == 60
    assert analytics.upgrade_recommendations() == []


def test_multiplas_organizacoes_apenas_as_qualificadas_aparecem():
    auth = FakeAuth(
        {
            "org_free_high_usage": {"plan": "free"},
            "org_free_low_usage": {"plan": "free"},
            "org_pro": {"plan": "pro"},
        }
    )
    usage = {"org_free_high_usage": 45, "org_free_low_usage": 1}
    analytics = BillingAnalytics(auth, get_usage=lambda org_id, metric: usage.get(org_id, 0))

    result = analytics.upgrade_recommendations()

    assert [r["org_id"] for r in result] == ["org_free_high_usage"]
