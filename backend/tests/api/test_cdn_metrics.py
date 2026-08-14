from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_metrics_endpoint_aceita_payload_minimo():
    c = _client()

    res = c.post("/api/v1/cdn/metrics", json={"event": "success"})

    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_metrics_endpoint_com_payload_completo():
    c = _client()

    res = c.post(
        "/api/v1/cdn/metrics",
        json={
            "event": "error",
            "domain": "cliente.com",
            "version": "v1",
            "duration": 120,
            "error": "timeout",
        },
    )

    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_metrics_endpoint_nao_exige_autenticacao():
    c = _client()

    res = c.post("/api/v1/cdn/metrics", json={"event": "success"})

    assert res.status_code == 200


def test_metrics_endpoint_payload_vazio_nao_quebra():
    c = _client()

    res = c.post("/api/v1/cdn/metrics", json={})

    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_metrics_endpoint_json_invalido_retorna_ok_false():
    c = _client()

    res = c.post(
        "/api/v1/cdn/metrics",
        content=b"not json at all",
        headers={"Content-Type": "application/json"},
    )

    assert res.status_code == 200
    assert res.json()["ok"] is False


def test_metrics_endpoint_payload_nao_e_objeto_nao_quebra():
    """A structurally valid JSON body that isn't a dict (e.g. a bare array or
    string) must not 500 — this endpoint is public and unauthenticated by
    design, so malformed input has to degrade gracefully, not crash."""
    c = _client()

    res = c.post("/api/v1/cdn/metrics", json=["not", "a", "dict"])

    assert res.status_code == 200
    assert res.json()["ok"] is False
