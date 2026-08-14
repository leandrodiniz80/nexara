"""Tests for format_generic()/format_slack() (Sprint 258).

Real bug in the spec's own version, fixed here — see alert_formatter.py's
own docstring: `alert.get("error_rate")`/`alert.get("avg_duration")` read
directly off the top-level alert dict would always be `None`, since
`detect_anomalies()` never puts those keys there — only nested under
`alert["current"]`. These tests build an alert exactly the way
`detect_anomalies()` actually does, to prove the formatters surface real
values, not silently-always-None ones.
"""

from app.platform.metrics.alert_formatter import format_generic, format_slack


def _alert(**overrides) -> dict:
    alert = {
        "domain": "broken.com",
        "type": "error",
        "severity": "critical",
        "current": {"error_rate": 0.8, "avg_duration": 450.0, "total": 100},
        "baseline": {"error_rate": 0.02, "avg_duration": 50.0, "total": 500},
    }
    alert.update(overrides)
    return alert


def test_format_generic_le_error_rate_e_latency_do_current_nao_do_topo():
    payload = format_generic(_alert())

    assert payload["error_rate"] == 0.8
    assert payload["latency"] == 450.0


def test_format_generic_inclui_domain_severity_e_type():
    payload = format_generic(_alert())

    assert payload["domain"] == "broken.com"
    assert payload["severity"] == "critical"
    assert payload["type"] == "error"


def test_format_generic_com_current_ausente_nao_lanca_erro():
    alert = _alert()
    del alert["current"]

    payload = format_generic(alert)

    assert payload["error_rate"] is None
    assert payload["latency"] is None


def test_format_slack_le_error_rate_e_latency_do_current():
    payload = format_slack(_alert())

    text = payload["blocks"][0]["text"]["text"]
    assert "0.8" in text
    assert "450.0" in text


def test_format_slack_inclui_domain_no_text_de_fallback():
    payload = format_slack(_alert())

    assert "broken.com" in payload["text"]


def test_format_slack_shape_tem_blocks_e_text():
    payload = format_slack(_alert())

    assert "text" in payload
    assert "blocks" in payload
    assert payload["blocks"][0]["type"] == "section"
