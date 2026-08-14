"""Tests for UsageAlerts (Sprint 271).

`get_usage`/`get_limit` here are plain lambdas/dicts, not whole
`UsageTracker`/`PlatformAuth` instances (the spec's own
`__init__(self, usage_tracker, auth)`) — see usage_alerts.py's own
docstring for why this class is built against two callables instead, and
why it's constructed directly in the router rather than wired as a
storage capability.
"""

from app.platform.usage.usage_alerts import UsageAlerts, build_upgrade_message


def _alerts(usage: int, limit: int) -> UsageAlerts:
    return UsageAlerts(get_usage=lambda t, m: usage, get_limit=lambda t, m: limit)


def test_abaixo_de_80_por_cento_nao_gera_alerta():
    alerts = _alerts(usage=39, limit=50)

    assert alerts.check_threshold("tenant-a", "alerts_sent") is None


def test_exatamente_80_por_cento_gera_warning():
    alerts = _alerts(usage=40, limit=50)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["level"] == "warning"
    assert result["used"] == 40
    assert result["limit"] == 50


def test_entre_80_e_100_por_cento_gera_warning():
    alerts = _alerts(usage=45, limit=50)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["level"] == "warning"


def test_exatamente_100_por_cento_gera_hard_limit():
    alerts = _alerts(usage=50, limit=50)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["level"] == "hard_limit"
    assert result["used"] == 50
    assert result["limit"] == 50


def test_acima_de_100_por_cento_ainda_e_hard_limit():
    alerts = _alerts(usage=75, limit=50)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["level"] == "hard_limit"


def test_plano_ilimitado_nunca_gera_alerta():
    """limit == -1 (the established "unlimited" sentinel, e.g. the
    enterprise plan) — never triggers, regardless of usage."""
    alerts = _alerts(usage=999_999, limit=-1)

    assert alerts.check_threshold("tenant-a", "alerts_sent") is None


def test_zero_uso_nao_gera_alerta():
    alerts = _alerts(usage=0, limit=50)

    assert alerts.check_threshold("tenant-a", "alerts_sent") is None


def test_limite_zero_com_uso_e_hard_limit_sem_erro():
    """Guards against ZeroDivisionError (the spec's own `used / limit`
    would raise) — a zero-limit plan with any usage at all is
    unambiguously at its hard limit, not silently "no signal"."""
    alerts = _alerts(usage=1, limit=0)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["level"] == "hard_limit"


def test_limite_zero_sem_uso_nao_gera_alerta():
    alerts = _alerts(usage=0, limit=0)

    assert alerts.check_threshold("tenant-a", "alerts_sent") is None


def test_resultado_inclui_mensagem_de_upgrade():
    alerts = _alerts(usage=50, limit=50)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["message"] is not None
    assert "upgrade" in result["message"].lower() or "Faça upgrade" in result["message"]


def test_get_usage_e_get_limit_recebem_tenant_id_e_metric():
    seen = []
    alerts = UsageAlerts(
        get_usage=lambda t, m: seen.append(("usage", t, m)) or 40,
        get_limit=lambda t, m: seen.append(("limit", t, m)) or 50,
    )

    alerts.check_threshold("tenant-a", "alerts_sent")

    assert ("limit", "tenant-a", "alerts_sent") in seen
    assert ("usage", "tenant-a", "alerts_sent") in seen


def test_usage_metric_e_limit_metric_podem_ser_diferentes():
    """UsageTracker (Sprint 270) tracks usage under "alerts_sent" while
    PlatformAuth's plan limits (Sprint 265) store the cap under
    "alerts_per_hour" — check_threshold() must query each callable with
    its own metric name, not force one shared name onto both."""
    seen = []
    alerts = UsageAlerts(
        get_usage=lambda t, m: seen.append(("usage", m)) or 40,
        get_limit=lambda t, m: seen.append(("limit", m)) or 50,
    )

    result = alerts.check_threshold("tenant-a", "alerts_sent", "alerts_per_hour")

    assert ("limit", "alerts_per_hour") in seen
    assert ("usage", "alerts_sent") in seen
    assert result["level"] == "warning"


def test_limit_metric_omitido_usa_o_mesmo_nome_do_usage_metric():
    alerts = _alerts(usage=50, limit=50)

    result = alerts.check_threshold("tenant-a", "alerts_sent")

    assert result["level"] == "hard_limit"


# --- build_upgrade_message() ------------------------------------------


def test_build_upgrade_message_warning():
    message = build_upgrade_message("warning", 40, 50)

    assert message == "Você já usou 40/50 alertas. Considere upgrade."


def test_build_upgrade_message_hard_limit():
    message = build_upgrade_message("hard_limit", 50, 50)

    assert message == "Limite atingido (50/50). Faça upgrade para continuar."


def test_build_upgrade_message_nivel_desconhecido_retorna_none():
    assert build_upgrade_message("something-else", 1, 2) is None
