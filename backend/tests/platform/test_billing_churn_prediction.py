"""Tests for BillingAnalytics.predict_churn() (Sprint 277)."""

import time

from app.platform.billing.billing_analytics import BillingAnalytics

_DAY = 86400


def _days_ago(n: int) -> int:
    return int(time.time()) - n * _DAY


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return self._orgs


def test_past_due_e_risco_alto():
    auth = FakeAuth(
        {
            "org_1": {
                "plan": "pro",
                "subscription_status": "past_due",
                "created_at": _days_ago(60),
            }
        }
    )

    result = BillingAnalytics(auth).predict_churn()

    assert result == [{"org_id": "org_1", "risk": "high", "reason": "payment_failed"}]


def test_score_baixo_e_risco_medio():
    """A canceled free-plan org scores 20 (< 50) but isn't past_due, so
    it falls through to the health-score rule."""
    auth = FakeAuth(
        {
            "org_1": {
                "plan": "free",
                "subscription_status": "canceled",
                "created_at": _days_ago(5),
            }
        }
    )

    result = BillingAnalytics(auth).predict_churn()

    assert result == [{"org_id": "org_1", "risk": "medium", "reason": "low_health"}]


def test_free_inativo_e_risco_medio():
    """Free, active, healthy-scoring (30 active + 20 no-failure = 50, at
    the >=50 boundary so it's not "low_health"), but signed up over 60
    days ago with no upgrade -> inactive_free."""
    auth = FakeAuth(
        {"org_1": {"plan": "free", "subscription_status": "active", "created_at": _days_ago(90)}}
    )

    result = BillingAnalytics(auth).predict_churn()

    assert result == [{"org_id": "org_1", "risk": "medium", "reason": "inactive_free"}]


def test_organizacao_saudavel_e_risco_baixo():
    auth = FakeAuth(
        {
            "org_1": {
                "plan": "pro",
                "subscription_status": "active",
                "created_at": _days_ago(60),
            }
        }
    )

    result = BillingAnalytics(auth).predict_churn()

    assert result == [{"org_id": "org_1", "risk": "low", "reason": "healthy"}]


def test_past_due_tem_prioridade_sobre_score_baixo():
    """An org that is both past_due (would also score low) must be
    classified by the higher-priority payment_failed rule, not
    low_health."""
    auth = FakeAuth(
        {
            "org_1": {
                "plan": "free",
                "subscription_status": "past_due",
                "created_at": _days_ago(5),
            }
        }
    )

    result = BillingAnalytics(auth).predict_churn()

    assert result == [{"org_id": "org_1", "risk": "high", "reason": "payment_failed"}]


def test_score_baixo_tem_prioridade_sobre_free_inativo():
    """A free org over 60 days old that also scores under 50 (e.g.
    canceled) is low_health, not inactive_free -- the rule table's order
    is a priority order, checked top to bottom."""
    auth = FakeAuth(
        {
            "org_1": {
                "plan": "free",
                "subscription_status": "canceled",
                "created_at": _days_ago(90),
            }
        }
    )

    result = BillingAnalytics(auth).predict_churn()

    assert result == [{"org_id": "org_1", "risk": "medium", "reason": "low_health"}]


def test_org_id_presente_para_cada_organizacao():
    auth = FakeAuth(
        {
            "org_a": {"plan": "pro", "created_at": _days_ago(60)},
            "org_b": {"plan": "enterprise", "created_at": _days_ago(60)},
        }
    )

    result = BillingAnalytics(auth).predict_churn()

    assert {r["org_id"] for r in result} == {"org_a", "org_b"}


def test_created_at_ausente_nao_gera_erro():
    auth = FakeAuth({"org_1": {"plan": "free"}})

    result = BillingAnalytics(auth).predict_churn()

    assert result[0]["org_id"] == "org_1"


def test_sem_organizacoes_retorna_lista_vazia():
    assert BillingAnalytics(FakeAuth({})).predict_churn() == []
