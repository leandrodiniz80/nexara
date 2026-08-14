"""Tests for BillingAnalytics's Sprint 275 methods (revenue_by_plan,
expansion_revenue, contraction_revenue, net_revenue_change).

`plan_history` here is written by hand into FakeAuth's org records — the
real PlatformAuth.set_organization_plan() writing it correctly is
covered separately in tests/platform/test_platform_auth.py.
"""

from app.platform.billing.billing_analytics import BillingAnalytics


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return self._orgs


def test_revenue_by_plan_segmenta_por_plano():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active"},
            "2": {"plan": "enterprise", "subscription_status": "active"},
        }
    )

    result = BillingAnalytics(auth).revenue_by_plan()

    assert result == {"pro": 99, "enterprise": 299}


def test_revenue_by_plan_soma_multiplas_orgs_no_mesmo_plano():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "subscription_status": "active"},
            "2": {"plan": "pro", "subscription_status": "active"},
        }
    )

    result = BillingAnalytics(auth).revenue_by_plan()

    assert result == {"pro": 198}


def test_revenue_by_plan_ignora_free():
    auth = FakeAuth({"1": {"plan": "free", "subscription_status": "active"}})

    assert BillingAnalytics(auth).revenue_by_plan() == {}


def test_revenue_by_plan_respeita_subscription_status():
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "canceled"}})

    assert BillingAnalytics(auth).revenue_by_plan() == {}


def test_revenue_by_plan_status_ausente_assume_active():
    auth = FakeAuth({"1": {"plan": "pro"}})

    assert BillingAnalytics(auth).revenue_by_plan() == {"pro": 99}


def test_revenue_by_plan_org_sem_plan_nao_gera_chave_none():
    """Guards against the spec's own bug: a plan-less org record must not
    add a spurious `None` key to the result — see billing_analytics.py's
    own docstring on revenue_by_plan()."""
    auth = FakeAuth({"1": {}})

    result = BillingAnalytics(auth).revenue_by_plan()

    assert None not in result
    assert result == {}


def test_expansion_revenue_soma_upgrades():
    auth = FakeAuth(
        {
            "1": {
                "plan_history": [
                    {"from": "free", "to": "pro"},
                    {"from": "pro", "to": "enterprise"},
                ]
            }
        }
    )

    assert BillingAnalytics(auth).expansion_revenue() == 99 + (299 - 99)


def test_expansion_revenue_ignora_downgrades():
    auth = FakeAuth({"1": {"plan_history": [{"from": "enterprise", "to": "pro"}]}})

    assert BillingAnalytics(auth).expansion_revenue() == 0


def test_expansion_revenue_org_sem_historico_e_zero():
    auth = FakeAuth({"1": {"plan": "pro"}})

    assert BillingAnalytics(auth).expansion_revenue() == 0


def test_contraction_revenue_soma_downgrades():
    auth = FakeAuth({"1": {"plan_history": [{"from": "enterprise", "to": "pro"}]}})

    assert BillingAnalytics(auth).contraction_revenue() == 299 - 99


def test_contraction_revenue_ignora_upgrades():
    auth = FakeAuth({"1": {"plan_history": [{"from": "free", "to": "pro"}]}})

    assert BillingAnalytics(auth).contraction_revenue() == 0


def test_net_revenue_change_e_expansion_menos_contraction():
    auth = FakeAuth(
        {
            "1": {"plan_history": [{"from": "free", "to": "enterprise"}]},
            "2": {"plan_history": [{"from": "enterprise", "to": "pro"}]},
        }
    )

    analytics = BillingAnalytics(auth)
    assert analytics.net_revenue_change() == analytics.expansion_revenue() - (
        analytics.contraction_revenue()
    )
    assert analytics.net_revenue_change() == 299 - (299 - 99)


def test_net_revenue_change_zero_sem_historico():
    auth = FakeAuth({"1": {"plan": "pro"}})

    assert BillingAnalytics(auth).net_revenue_change() == 0
