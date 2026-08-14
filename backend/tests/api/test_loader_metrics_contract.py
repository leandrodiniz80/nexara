"""Contract tests for the Sprint 242 telemetry additions to cdn/loader.v1.js.

The sprint's own spec example built the metrics URL as a bare relative path
("/api/v1/cdn/metrics") — the exact same bug already caught and fixed twice
before in this file (Sprint 237's fetch call, Sprint 240's retry logic): the
loader executes in the embedding page's own origin (e.g. "cliente.com"), so
a relative sendBeacon/fetch URL would hit the CUSTOMER's server, not the
Nexara API. The fix reuses the existing API_BASE constant, same as every
other network call in this file.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_loader_contem_endpoint_de_metrics():
    c = _client()

    res = c.get("/api/v1/cdn/loader.v1.js")
    body = res.text

    assert "/api/v1/cdn/metrics" in body


def test_loader_envia_metricas():
    c = _client()

    res = c.get("/api/v1/cdn/loader.v1.js")
    body = res.text

    assert "sendBeacon" in body
    assert "event" in body


def test_loader_metrics_usa_url_absoluta_nao_relativa():
    c = _client()

    body = c.get("/api/v1/cdn/loader.v1.js").text

    assert "var url = API_BASE + METRICS_PATH;" in body


def test_loader_tem_fallback_fetch_com_keepalive():
    c = _client()

    body = c.get("/api/v1/cdn/loader.v1.js").text

    assert "keepalive: true" in body


def test_loader_envia_evento_de_sucesso_com_duracao():
    c = _client()

    body = c.get("/api/v1/cdn/loader.v1.js").text

    assert 'event: "success"' in body
    assert "duration: Date.now() - start" in body


def test_loader_envia_evento_de_erro():
    c = _client()

    body = c.get("/api/v1/cdn/loader.v1.js").text

    assert 'event: "error"' in body


def test_loader_nao_duplica_metrica_de_falha():
    """The spec's own design fired two separate metrics for the same
    terminal failure ("error" from one catch block, "fatal" from another) —
    that double-counts a single fetch failure in any error-rate calculation
    downstream. This loader fires exactly one terminal-failure event."""
    c = _client()

    body = c.get("/api/v1/cdn/loader.v1.js").text

    # One definition + exactly two call sites (success, terminal error) —
    # not a third "fatal" call duplicating the same failure.
    assert body.count("sendMetric(") == 3
