"""Tests for BillingAnalytics's Sprint 274 methods (active_mrr, arr,
active_customers, churn_rate, ltv).

The spec's own `test_active_customers` used orgs with no `plan` key at
all and expected them to count — but `active_customers()` here requires
`plan != "free"` (missing `plan` defaults to `"free"`, same as everywhere
else in this codebase), matching `/billing/dashboard`'s own
`active_customers` (BillingMetrics, Sprint 272) so the two endpoints
don't report two different numbers for the same underlying data. See
billing_analytics.py's own docstring on `active_customers()` for why.
Rewritten below with explicit paying plans.
"""

from app.platform.billing.billing_analytics import BillingAnalytics


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return self._orgs


def test_active_mrr_only_active():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active"},
            "2": {"plan": "pro", "subscription_status": "canceled"},
        }
    )

    assert BillingAnalytics(auth).active_mrr() == 99


def test_active_mrr_inclui_trialing():
    auth = FakeAuth({"1": {"plan": "enterprise", "subscription_status": "trialing"}})

    assert BillingAnalytics(auth).active_mrr() == 299


def test_active_mrr_status_ausente_assume_active():
    """The manual-upgrade fallback (/billing/upgrade with no Stripe
    configured) sets a plan via set_organization_plan() and never
    touches subscription_status — such an org must still count as
    revenue, matching BillingMetrics.calculate()'s own default
    (Sprint 272), or /billing/dashboard and /billing/analytics would
    report different MRR for the same organization."""
    auth = FakeAuth({"1": {"plan": "pro"}})

    assert BillingAnalytics(auth).active_mrr() == 99


def test_arr_e_active_mrr_vezes_doze():
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "active"}})

    analytics = BillingAnalytics(auth)
    assert analytics.arr() == analytics.active_mrr() * 12


def test_active_customers_conta_apenas_pagantes_ativos():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active"},
            "2": {"plan": "enterprise", "subscription_status": "trialing"},
            "3": {"plan": "pro", "subscription_status": "canceled"},
        }
    )

    assert BillingAnalytics(auth).active_customers() == 2


def test_active_customers_exclui_plano_free():
    """A free-plan org with an "active"-ish (or missing) status is not a
    paying customer — must not inflate this count, or it would diverge
    from /billing/dashboard's own definition of active_customers."""
    auth = FakeAuth({"1": {"plan": "free", "subscription_status": "active"}})

    assert BillingAnalytics(auth).active_customers() == 0


def test_active_customers_status_ausente_assume_active():
    auth = FakeAuth({"1": {"plan": "pro"}})

    assert BillingAnalytics(auth).active_customers() == 1


def test_churn_rate_percentual_sobre_base_total():
    auth = FakeAuth(
        {
            "1": {"subscription_status": "active"},
            "2": {"subscription_status": "canceled"},
        }
    )

    assert BillingAnalytics(auth).churn_rate() == 50.0


def test_churn_rate_base_vazia_retorna_zero():
    assert BillingAnalytics(FakeAuth({})).churn_rate() == 0.0


def test_ltv_diferente_de_zero_com_clientes_pagantes():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active"},
            "2": {"plan": "pro", "subscription_status": "canceled"},
        }
    )

    assert BillingAnalytics(auth).ltv() > 0


def test_ltv_zero_sem_clientes_ativos():
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "canceled"}})

    assert BillingAnalytics(auth).ltv() == 0.0


def test_ltv_fallback_conservador_quando_churn_zero():
    """No churn at all (nothing canceled) falls back to a flat 12-month
    lifetime estimate rather than dividing by zero."""
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "active"}})

    analytics = BillingAnalytics(auth)
    assert analytics.ltv() == round(99 * 12, 2)
