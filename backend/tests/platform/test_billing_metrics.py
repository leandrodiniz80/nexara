"""Tests for BillingMetrics (Sprint 272).

FakeAuth exposes `list_organizations()`, not a bare `_organizations`
attribute — BillingMetrics reads organizations through that public
PlatformAuth method (see billing_metrics.py's own docstring for why the
spec's own `getattr(self._auth, "_organizations", {})` was replaced).
"""

from app.platform.billing.billing_metrics import BillingMetrics


class FakeAuth:
    def __init__(self, organizations: dict):
        self._orgs = organizations

    def list_organizations(self) -> dict:
        return self._orgs


def test_metrics_basico():
    metrics = BillingMetrics(
        FakeAuth(
            {
                "1": {"plan": "free", "subscription_status": "active"},
                "2": {"plan": "pro", "subscription_status": "active"},
                "3": {"plan": "enterprise", "subscription_status": "canceled"},
            }
        )
    ).calculate()

    assert metrics["mrr"] == 99 + 299
    assert metrics["arr"] == (99 + 299) * 12
    assert metrics["active_customers"] == 2
    assert metrics["total_customers"] == 3


def test_churn_rate_usa_total_de_clientes_nao_so_pagantes():
    metrics = BillingMetrics(
        FakeAuth(
            {
                "1": {"plan": "free", "subscription_status": "active"},
                "2": {"plan": "pro", "subscription_status": "canceled"},
                "3": {"plan": "pro", "subscription_status": "active"},
                "4": {"plan": "pro", "subscription_status": "active"},
            }
        )
    ).calculate()

    assert metrics["churn_rate"] == 1 / 4


def test_arpu_e_media_da_receita_sobre_clientes_ativos():
    metrics = BillingMetrics(
        FakeAuth(
            {
                "1": {"plan": "pro", "subscription_status": "active"},
                "2": {"plan": "enterprise", "subscription_status": "active"},
            }
        )
    ).calculate()

    assert metrics["arpu"] == (99 + 299) / 2


def test_ltv_e_arpu_dividido_pelo_churn():
    metrics = BillingMetrics(
        FakeAuth(
            {
                "1": {"plan": "pro", "subscription_status": "active"},
                "2": {"plan": "pro", "subscription_status": "canceled"},
            }
        )
    ).calculate()

    assert metrics["arpu"] == 99
    assert metrics["churn_rate"] == 1 / 2
    assert metrics["ltv"] == 99 / (1 / 2)


def test_organizacoes_vazias_nao_gera_erro_de_divisao():
    metrics = BillingMetrics(FakeAuth({})).calculate()

    assert metrics == {
        "mrr": 0,
        "arr": 0,
        "active_customers": 0,
        "total_customers": 0,
        "churn_rate": 0,
        "arpu": 0,
        "ltv": 0,
    }


def test_sem_clientes_ativos_nao_gera_erro_de_divisao():
    metrics = BillingMetrics(
        FakeAuth({"1": {"plan": "free", "subscription_status": "active"}})
    ).calculate()

    assert metrics["arpu"] == 0
    assert metrics["ltv"] == 0


def test_sem_churn_ltv_e_zero_nao_erro():
    metrics = BillingMetrics(
        FakeAuth({"1": {"plan": "pro", "subscription_status": "active"}})
    ).calculate()

    assert metrics["churn_rate"] == 0
    assert metrics["ltv"] == 0


def test_organizacao_sem_plan_ou_status_assume_defaults():
    """Missing `plan`/`subscription_status` keys default to "free"/
    "active" — mirrors PlatformAuth's own defaults for a freshly created
    organization (create_organization() always sets `plan: "free"`)."""
    metrics = BillingMetrics(FakeAuth({"1": {}})).calculate()

    assert metrics["mrr"] == 0
    assert metrics["active_customers"] == 0
    assert metrics["total_customers"] == 1
