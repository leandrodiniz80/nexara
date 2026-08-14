"""Tests for AlertInsights (Sprint 261) — pure aggregation over an
already-fetched incidents list, no store/storage dependency."""

from app.platform.metrics.alert_insights import AlertInsights


def _incident(domain: str, severity: str) -> dict:
    return {"domain": domain, "severity": severity}


def test_top_domains_by_alerts_ordena_por_contagem_decrescente():
    incidents = [
        _incident("a.com", "high"),
        _incident("b.com", "critical"),
        _incident("b.com", "critical"),
        _incident("b.com", "high"),
    ]

    top = AlertInsights.top_domains_by_alerts(incidents)

    assert top[0] == {"domain": "b.com", "count": 3}
    assert top[1] == {"domain": "a.com", "count": 1}


def test_top_domains_by_alerts_desempate_deterministico_por_nome():
    incidents = [_incident("z.com", "high"), _incident("a.com", "high")]

    top = AlertInsights.top_domains_by_alerts(incidents)

    assert [item["domain"] for item in top] == ["a.com", "z.com"]


def test_top_domains_by_alerts_limita_a_10():
    incidents = [_incident(f"d{i}.com", "high") for i in range(15)]

    top = AlertInsights.top_domains_by_alerts(incidents)

    assert len(top) == 10


def test_top_domains_by_alerts_vazio_sem_incidentes():
    assert AlertInsights.top_domains_by_alerts([]) == []


def test_severity_distribution_conta_cada_severidade():
    incidents = [
        _incident("a.com", "critical"),
        _incident("b.com", "critical"),
        _incident("c.com", "high"),
        _incident("d.com", "medium"),
    ]

    dist = AlertInsights.severity_distribution(incidents)

    assert dist == {"critical": 2, "high": 1, "medium": 1, "low": 0}


def test_severity_distribution_zerado_sem_incidentes():
    assert AlertInsights.severity_distribution([]) == {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }


def test_severity_distribution_ignora_severidade_desconhecida():
    incidents = [_incident("a.com", "unknown-severity")]

    dist = AlertInsights.severity_distribution(incidents)

    assert dist == {"critical": 0, "high": 0, "medium": 0, "low": 0}


def test_affected_domains_conta_dominios_unicos():
    incidents = [
        _incident("a.com", "critical"),
        _incident("a.com", "high"),
        _incident("b.com", "critical"),
    ]

    assert AlertInsights.affected_domains(incidents) == 2


def test_affected_domains_zero_sem_incidentes():
    assert AlertInsights.affected_domains([]) == 0
