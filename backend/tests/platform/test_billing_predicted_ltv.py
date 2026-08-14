"""Tests for BillingAnalytics.predicted_ltv() (Sprint 277).

"Weighted average of customers" (the spec's own phrasing) doesn't say
what the weight should be -- weighted here by each organization's own
MRR contribution (get_plan_price), the one number in this file that
already represents how much a customer matters to revenue. See
predicted_ltv()'s own docstring for the full reasoning.
"""

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


def test_sem_organizacoes_retorna_zero():
    assert BillingAnalytics(FakeAuth({})).predicted_ltv() == 0.0


def test_sem_clientes_pagantes_retorna_zero():
    auth = FakeAuth({"1": {"plan": "free", "subscription_status": "active"}})

    assert BillingAnalytics(auth).predicted_ltv() == 0.0


def test_churn_baixo_mantem_ltv_base():
    """Every paying org is low-risk -> the discount is 0% everywhere, so
    the weighted average equals the unadjusted base ltv() exactly."""
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active", "created_at": _days_ago(60)},
            "2": {
                "plan": "enterprise",
                "subscription_status": "active",
                "created_at": _days_ago(60),
            },
        }
    )
    analytics = BillingAnalytics(auth)

    assert analytics.predicted_ltv() == analytics.ltv()


def test_churn_alto_reduz_ltv():
    """A past_due (high-risk) organization pulls the weighted average
    below the unadjusted base ltv(), even though it doesn't count toward
    active_mrr/active_customers itself."""
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active", "created_at": _days_ago(60)},
            "2": {
                "plan": "enterprise",
                "subscription_status": "past_due",
                "created_at": _days_ago(60),
            },
        }
    )
    analytics = BillingAnalytics(auth)

    base_ltv = analytics.ltv()
    predicted = analytics.predicted_ltv()

    assert predicted < base_ltv
    # base_ltv = round(99 * 12, 2) = 1188.0 (only org "1" is active/paying)
    assert base_ltv == 1188.0
    # weighted: (1188.0 * 99 + (1188.0 * 0.6) * 299) / (99 + 299) = 831.0030...
    assert predicted == 831.0


def test_organizacao_free_nao_afeta_a_media_ponderada():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active", "created_at": _days_ago(60)},
            "2": {"plan": "free", "subscription_status": "past_due", "created_at": _days_ago(60)},
        }
    )
    analytics = BillingAnalytics(auth)

    # org "2" is free -> weight 0 -> contributes nothing regardless of risk
    assert analytics.predicted_ltv() == analytics.ltv()


def test_resultado_e_float_arredondado():
    auth = FakeAuth(
        {"1": {"plan": "pro", "subscription_status": "active", "created_at": _days_ago(60)}}
    )

    result = BillingAnalytics(auth).predicted_ltv()

    assert isinstance(result, float)
    assert result == round(result, 2)
