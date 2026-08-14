"""Tests for BillingAnalytics.pricing_experiment_metrics() and
recommend_price_adjustment() (Sprint 282).

org_ids used below are pre-discovered (at module load, via the same
search helper as test_pricing_experiments.py) real SHA-256-mapped
examples of each variant -- there's no way to hand-pick a preimage, so
tests build FakeAuth org data keyed to whichever real ids land in each
bucket.
"""

from app.platform.billing.billing_analytics import BillingAnalytics
from app.platform.billing.pricing_experiments import PricingExperimentEngine

_engine = PricingExperimentEngine(auth=None)


def _org_ids_for_variant(variant: str, count: int) -> list[str]:
    found = []
    i = 0

    while len(found) < count:
        org_id = f"acme-{i}"
        if _engine.assign_variant(org_id) == variant:
            found.append(org_id)
        i += 1

        if i > 100_000:
            raise RuntimeError(f"could not find {count} org_ids for variant {variant}")

    return found


class FakeAuth:
    def __init__(self, orgs: dict):
        self._orgs = orgs

    def list_organizations(self) -> dict:
        return dict(self._orgs)


def _org(plan: str) -> dict:
    return {"plan": plan}


# --- pricing_experiment_metrics() -------------------------------------


def test_metrics_retorna_os_tres_grupos():
    analytics = BillingAnalytics(FakeAuth({}))

    metrics = analytics.pricing_experiment_metrics()

    assert set(metrics.keys()) == {"control", "price_up", "price_down"}
    for group in metrics.values():
        assert group == {"conversion_rate": 0.0, "mrr": 0.0}


def test_conversion_rate_reflete_organizacoes_pagantes_reais():
    control_ids = _org_ids_for_variant("control", 2)
    orgs = {
        control_ids[0]: _org("pro"),
        control_ids[1]: _org("free"),
    }
    analytics = BillingAnalytics(FakeAuth(orgs))

    metrics = analytics.pricing_experiment_metrics()

    assert metrics["control"]["conversion_rate"] == 0.5


def test_mrr_e_simulado_com_o_multiplicador_da_variante():
    price_up_ids = _org_ids_for_variant("price_up", 1)
    orgs = {price_up_ids[0]: _org("pro")}
    analytics = BillingAnalytics(FakeAuth(orgs))

    metrics = analytics.pricing_experiment_metrics()

    assert metrics["price_up"]["mrr"] == round(99 * 1.2, 2)


def test_org_free_nao_conta_como_pagante_nem_gera_mrr():
    control_ids = _org_ids_for_variant("control", 1)
    orgs = {control_ids[0]: _org("free")}
    analytics = BillingAnalytics(FakeAuth(orgs))

    metrics = analytics.pricing_experiment_metrics()

    assert metrics["control"]["conversion_rate"] == 0.0
    assert metrics["control"]["mrr"] == 0.0


# --- recommend_price_adjustment() ---------------------------------------


def test_recomenda_increase_quando_price_up_gera_mais_mrr_sem_cair_conversao():
    control_ids = _org_ids_for_variant("control", 2)
    price_up_ids = _org_ids_for_variant("price_up", 2)
    orgs = {
        control_ids[0]: _org("pro"),
        control_ids[1]: _org("free"),
        price_up_ids[0]: _org("pro"),
        price_up_ids[1]: _org("pro"),
    }
    analytics = BillingAnalytics(FakeAuth(orgs))

    result = analytics.recommend_price_adjustment()

    assert result["recommended_strategy"] == "increase"
    assert result["confidence"] > 0


def test_recomenda_decrease_quando_price_down_aumenta_muito_a_conversao():
    control_ids = _org_ids_for_variant("control", 2)
    price_up_ids = _org_ids_for_variant("price_up", 2)
    price_down_ids = _org_ids_for_variant("price_down", 2)
    orgs = {
        control_ids[0]: _org("pro"),
        control_ids[1]: _org("free"),
        price_up_ids[0]: _org("free"),
        price_up_ids[1]: _org("free"),
        price_down_ids[0]: _org("pro"),
        price_down_ids[1]: _org("pro"),
    }
    analytics = BillingAnalytics(FakeAuth(orgs))

    result = analytics.recommend_price_adjustment()

    assert result["recommended_strategy"] == "decrease"
    assert result["confidence"] > 0


def test_recomenda_keep_quando_nenhuma_variante_supera_o_control():
    control_ids = _org_ids_for_variant("control", 2)
    price_up_ids = _org_ids_for_variant("price_up", 2)
    price_down_ids = _org_ids_for_variant("price_down", 2)
    orgs = {
        control_ids[0]: _org("pro"),
        control_ids[1]: _org("free"),
        price_up_ids[0]: _org("free"),
        price_up_ids[1]: _org("free"),
        price_down_ids[0]: _org("pro"),
        price_down_ids[1]: _org("free"),
    }
    analytics = BillingAnalytics(FakeAuth(orgs))

    result = analytics.recommend_price_adjustment()

    assert result["recommended_strategy"] == "keep"
    assert result["confidence"] == 0.0


def test_recomendacao_sem_organizacoes_e_keep():
    analytics = BillingAnalytics(FakeAuth({}))

    result = analytics.recommend_price_adjustment()

    assert result["recommended_strategy"] == "keep"


def test_recomendacao_inclui_reason_legivel():
    analytics = BillingAnalytics(FakeAuth({}))

    result = analytics.recommend_price_adjustment()

    assert isinstance(result["reason"], str)
    assert len(result["reason"]) > 0
