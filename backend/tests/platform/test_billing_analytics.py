"""Tests for BillingAnalytics (Sprint 273).

FakeAuth.list_organizations() returns a dict keyed by org_id
({org_id: org_data}), matching the real PlatformAuth.list_organizations()
shape (Sprint 272) — the spec's own tests passed a bare list, which
doesn't match that shape and would have hidden the real
`for org in orgs:` key-vs-value iteration bug (see billing_analytics.py's
own docstring). `created_at`/`canceled_at` are Unix timestamps (ints),
matching how PlatformAuth.create_organization()/set_subscription_status()
actually persist them — not ISO strings, which is what the spec's own
tests used and which real records never contain.
"""

from datetime import datetime, timezone

from app.platform.billing.billing_analytics import BillingAnalytics


def _ts(year: int, month: int, day: int = 1) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return self._orgs


def test_revenue_timeseries_agrupa_por_mes_de_criacao():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "created_at": _ts(2026, 1, 10)},
            "2": {"plan": "pro", "created_at": _ts(2026, 1, 15)},
        }
    )

    result = BillingAnalytics(auth).revenue_timeseries()

    assert result == [{"month": "2026-01", "revenue": 198}]


def test_revenue_timeseries_ordena_meses_cronologicamente():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "created_at": _ts(2026, 3, 1)},
            "2": {"plan": "enterprise", "created_at": _ts(2026, 1, 1)},
        }
    )

    result = BillingAnalytics(auth).revenue_timeseries()

    assert [r["month"] for r in result] == ["2026-01", "2026-03"]


def test_revenue_timeseries_ignora_org_sem_created_at():
    auth = FakeAuth({"1": {"plan": "pro"}})

    result = BillingAnalytics(auth).revenue_timeseries()

    assert result == []


def test_growth_rate_zero_com_um_unico_mes():
    auth = FakeAuth({"1": {"plan": "pro", "created_at": _ts(2026, 1, 10)}})

    assert BillingAnalytics(auth).growth_rate() == 0.0


def test_growth_rate_calcula_variacao_percentual():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "created_at": _ts(2026, 1, 1)},
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
            "3": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
        }
    )

    assert BillingAnalytics(auth).growth_rate() == 100.0


def test_growth_rate_zero_quando_mes_anterior_e_zero():
    auth = FakeAuth(
        {
            "1": {"plan": "free", "created_at": _ts(2026, 1, 1)},
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
        }
    )

    assert BillingAnalytics(auth).growth_rate() == 0.0


def test_plan_distribution_conta_por_plano():
    auth = FakeAuth(
        {
            "1": {"plan": "free"},
            "2": {"plan": "pro"},
            "3": {"plan": "pro"},
        }
    )

    dist = BillingAnalytics(auth).plan_distribution()

    assert dist["pro"] == 2
    assert dist["free"] == 1


def test_plan_distribution_org_sem_plan_conta_como_free():
    auth = FakeAuth({"1": {}})

    dist = BillingAnalytics(auth).plan_distribution()

    assert dist["free"] == 1


def test_churn_over_time_agrupa_por_mes_de_cancelamento():
    auth = FakeAuth(
        {
            "1": {
                "plan": "pro",
                "subscription_status": "canceled",
                "canceled_at": _ts(2026, 2, 1),
            }
        }
    )

    result = BillingAnalytics(auth).churn_over_time()

    assert result == [{"month": "2026-02", "churned": 1}]


def test_churn_over_time_ignora_org_nao_cancelada():
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "active"}})

    assert BillingAnalytics(auth).churn_over_time() == []


def test_churn_over_time_ignora_cancelada_sem_canceled_at():
    """A subscription_status stuck at "canceled" without a canceled_at
    timestamp (e.g. data from before this sprint) is skipped rather than
    crashing or silently defaulting to some arbitrary month."""
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "canceled"}})

    assert BillingAnalytics(auth).churn_over_time() == []


def test_organizacoes_vazias_nao_gera_erro():
    auth = FakeAuth({})
    analytics = BillingAnalytics(auth)

    assert analytics.revenue_timeseries() == []
    assert analytics.growth_rate() == 0.0
    assert analytics.plan_distribution() == {}
    assert analytics.churn_over_time() == []
