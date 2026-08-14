"""Tests for BillingAnalytics.forecast_mrr() (Sprint 276)."""

from datetime import datetime, timezone

from app.platform.billing.billing_analytics import BillingAnalytics


def _ts(year: int, month: int, day: int = 1) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return self._orgs


def test_forecast_sem_dados_retorna_lista_vazia():
    assert BillingAnalytics(FakeAuth({})).forecast_mrr() == []


def test_forecast_crescimento_zero_com_um_unico_mes():
    auth = FakeAuth({"1": {"plan": "pro", "created_at": _ts(2026, 1, 1)}})

    forecast = BillingAnalytics(auth).forecast_mrr(months=2)

    assert forecast == [
        {"month": "2026-02", "projected_mrr": 99},
        {"month": "2026-03", "projected_mrr": 99},
    ]


def test_forecast_crescimento_zero_entre_meses_iguais():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "created_at": _ts(2026, 1, 1)},
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
        }
    )

    forecast = BillingAnalytics(auth).forecast_mrr(months=1)

    assert forecast == [{"month": "2026-03", "projected_mrr": 99}]


def test_forecast_crescimento_positivo_projeta_composto():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "created_at": _ts(2026, 1, 1)},
            "2": {"plan": "enterprise", "created_at": _ts(2026, 2, 1)},
        }
    )

    forecast = BillingAnalytics(auth).forecast_mrr(months=1)

    # growth = (299 - 99) / 99; next revenue = round(299 * (1 + growth))
    assert forecast == [{"month": "2026-03", "projected_mrr": 903}]


def test_forecast_usa_apenas_ultimos_3_meses():
    auth = FakeAuth(
        {
            "1": {"plan": "free", "created_at": _ts(2026, 1, 1)},
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
            "3": {"plan": "pro", "created_at": _ts(2026, 3, 1)},
            "4": {"plan": "enterprise", "created_at": _ts(2026, 4, 1)},
        }
    )

    forecast = BillingAnalytics(auth).forecast_mrr(months=1)

    # January's 0 -> 99 jump must not factor into the average growth rate
    # used here; only Feb/Mar/Apr's two pairwise rates should.
    assert forecast == [{"month": "2026-05", "projected_mrr": 601}]


def test_forecast_ignora_par_com_base_zero_sem_erro():
    auth = FakeAuth(
        {
            "1": {"plan": "free", "created_at": _ts(2026, 1, 1)},
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
        }
    )

    forecast = BillingAnalytics(auth).forecast_mrr(months=1)

    assert forecast == [{"month": "2026-03", "projected_mrr": 99}]


def test_forecast_retorna_quantidade_de_meses_solicitada():
    auth = FakeAuth({"1": {"plan": "pro", "created_at": _ts(2026, 1, 1)}})

    forecast = BillingAnalytics(auth).forecast_mrr(months=3)

    assert [f["month"] for f in forecast] == ["2026-02", "2026-03", "2026-04"]
