"""Tests for BillingAnalytics.detect_revenue_anomalies() (Sprint 276)."""

from datetime import datetime, timezone

from app.platform.billing.billing_analytics import BillingAnalytics


def _ts(year: int, month: int, day: int = 1) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return self._orgs


def test_sem_dados_retorna_lista_vazia():
    assert BillingAnalytics(FakeAuth({})).detect_revenue_anomalies() == []


def test_primeiro_mes_nunca_e_reportado():
    """A single month has nothing to compare against — no anomaly, no
    IndexError."""
    auth = FakeAuth({"1": {"plan": "enterprise", "created_at": _ts(2026, 1, 1)}})

    assert BillingAnalytics(auth).detect_revenue_anomalies() == []


def test_queda_acima_de_30_por_cento_e_detectada():
    auth = FakeAuth(
        {
            "1": {"plan": "enterprise", "created_at": _ts(2026, 1, 1)},  # 299
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},  # 99
        }
    )

    anomalies = BillingAnalytics(auth).detect_revenue_anomalies()

    assert anomalies == [{"month": "2026-02", "change": -66.89, "type": "drop"}]


def test_crescimento_acima_de_30_por_cento_e_detectado():
    auth = FakeAuth(
        {
            "1": {"plan": "pro", "created_at": _ts(2026, 1, 1)},  # 99
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
            "3": {"plan": "pro", "created_at": _ts(2026, 2, 1)},
            "4": {"plan": "pro", "created_at": _ts(2026, 2, 1)},  # 297 total
        }
    )

    anomalies = BillingAnalytics(auth).detect_revenue_anomalies()

    assert anomalies == [{"month": "2026-02", "change": 200.0, "type": "spike"}]


def test_meses_normais_sao_ignorados():
    auth = FakeAuth(
        {
            "1": {"plan": "enterprise", "created_at": _ts(2026, 1, 1)},  # 299
            "2": {"plan": "pro", "created_at": _ts(2026, 2, 1)},  # 99 -> drop
            "3": {"plan": "pro", "created_at": _ts(2026, 3, 1)},  # 99 -> flat
        }
    )

    anomalies = BillingAnalytics(auth).detect_revenue_anomalies()

    months_reported = [a["month"] for a in anomalies]
    assert "2026-03" not in months_reported


def test_variacao_de_exatos_30_por_cento_nao_e_anomalia():
    """The rule is "> 30%", strictly — exactly 30% must not be flagged."""
    orgs = {f"prev-{i}": {"plan": "pro", "created_at": _ts(2026, 1, 1)} for i in range(10)}
    orgs.update(
        {f"curr-{i}": {"plan": "pro", "created_at": _ts(2026, 2, 1)} for i in range(13)}
    )
    auth = FakeAuth(orgs)

    # prev = 10 * 99 = 990; curr = 13 * 99 = 1287; change = 297 / 990 = 30.0%
    assert BillingAnalytics(auth).detect_revenue_anomalies() == []


def test_variacao_logo_acima_de_30_por_cento_e_anomalia():
    orgs = {f"prev-{i}": {"plan": "pro", "created_at": _ts(2026, 1, 1)} for i in range(10)}
    orgs.update(
        {f"curr-{i}": {"plan": "pro", "created_at": _ts(2026, 2, 1)} for i in range(14)}
    )
    auth = FakeAuth(orgs)

    anomalies = BillingAnalytics(auth).detect_revenue_anomalies()

    assert anomalies == [{"month": "2026-02", "change": 40.0, "type": "spike"}]


def test_par_com_base_zero_e_ignorado_sem_erro():
    auth = FakeAuth(
        {
            "1": {"plan": "free", "created_at": _ts(2026, 1, 1)},  # 0
            "2": {"plan": "enterprise", "created_at": _ts(2026, 2, 1)},  # 299
        }
    )

    assert BillingAnalytics(auth).detect_revenue_anomalies() == []
