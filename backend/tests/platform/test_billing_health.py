"""Tests for BillingAnalytics.customer_health_score() (Sprint 276).

`subscription_status` is a single field, so "canceled" and "past_due"
("failed payment") are mutually exclusive states in this data model —
tested here as separate low-scoring scenarios rather than combined, as
a literal "cancelado + failed" org can't exist.
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


def test_score_alto_enterprise_ativo_estabelecido():
    auth = FakeAuth(
        {
            "1": {
                "plan": "enterprise",
                "subscription_status": "active",
                "created_at": _days_ago(60),
            }
        }
    )

    result = BillingAnalytics(auth).customer_health_score()

    assert result["average_score"] == 100
    assert result["distribution"] == {"healthy": 1, "risk": 0, "critical": 0}


def test_score_risco_plano_pago_cancelado():
    auth = FakeAuth(
        {
            "1": {
                "plan": "pro",
                "subscription_status": "canceled",
                "created_at": _days_ago(60),
            }
        }
    )

    result = BillingAnalytics(auth).customer_health_score()

    # paid (+40) + canceled (+0) + no payment failure (+20) + tenure (+10) = 70
    assert result["average_score"] == 70
    assert result["distribution"] == {"healthy": 0, "risk": 1, "critical": 0}


def test_score_critico_free_com_falha_de_pagamento_e_recem_criado():
    auth = FakeAuth(
        {
            "1": {
                "plan": "free",
                "subscription_status": "past_due",
                "created_at": _days_ago(5),
            }
        }
    )

    result = BillingAnalytics(auth).customer_health_score()

    # free (+0) + not canceled (+30) + payment failure (+0) + young (+0) = 30
    assert result["average_score"] == 30
    assert result["distribution"] == {"healthy": 0, "risk": 0, "critical": 1}


def test_score_critico_free_cancelado_recem_criado():
    auth = FakeAuth(
        {"1": {"plan": "free", "subscription_status": "canceled", "created_at": _days_ago(5)}}
    )

    result = BillingAnalytics(auth).customer_health_score()

    # free (+0) + canceled (+0) + no payment failure (+20) + young (+0) = 20
    assert result["average_score"] == 20
    assert result["distribution"] == {"healthy": 0, "risk": 0, "critical": 1}


def test_distribuicao_correta_com_base_mista():
    auth = FakeAuth(
        {
            "healthy": {
                "plan": "enterprise",
                "subscription_status": "active",
                "created_at": _days_ago(60),
            },
            "risk": {
                "plan": "pro",
                "subscription_status": "canceled",
                "created_at": _days_ago(60),
            },
            "critical_1": {
                "plan": "free",
                "subscription_status": "past_due",
                "created_at": _days_ago(5),
            },
            "critical_2": {
                "plan": "free",
                "subscription_status": "canceled",
                "created_at": _days_ago(5),
            },
        }
    )

    result = BillingAnalytics(auth).customer_health_score()

    assert result["distribution"] == {"healthy": 1, "risk": 1, "critical": 2}
    assert result["average_score"] == round((100 + 70 + 30 + 20) / 4)


def test_organizacao_sem_created_at_nao_ganha_pontos_de_tenure():
    auth = FakeAuth({"1": {"plan": "pro", "subscription_status": "active"}})

    result = BillingAnalytics(auth).customer_health_score()

    # paid (+40) + active (+30) + no failure (+20), no created_at -> no +10
    assert result["average_score"] == 90


def test_status_ausente_assume_active():
    auth = FakeAuth({"1": {"plan": "pro", "created_at": _days_ago(60)}})

    result = BillingAnalytics(auth).customer_health_score()

    assert result["average_score"] == 100


def test_sem_organizacoes_nao_gera_erro_de_divisao():
    result = BillingAnalytics(FakeAuth({})).customer_health_score()

    assert result == {
        "average_score": 0,
        "distribution": {"healthy": 0, "risk": 0, "critical": 0},
    }
