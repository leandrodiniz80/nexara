from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_ok_status_version_and_uptime():
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert "version" in body["data"]
    assert body["data"]["uptime"] >= 0


def test_health_response_uses_the_api_response_envelope():
    client = _client()

    body = client.get("/health").json()

    assert set(body.keys()) == {
        "success",
        "data",
        "errors",
        "warnings",
        "request_id",
        "execution_time",
        "timestamp",
    }
    assert body["errors"] == []
    assert body["warnings"] == []


def test_health_response_includes_a_request_id_header():
    client = _client()

    response = client.get("/health")

    assert "X-Request-ID" in response.headers
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_health_includes_components():
    client = _client()

    response = client.get("/health")

    components = response.json()["data"]["components"]
    assert components["auth"] == "ok"
    assert components["storage"] in {"ok", "disabled"}
    assert components["cache"] in {"ok", "disabled"}
    assert components["stripe"] in {"ok", "disabled"}


def test_health_stripe_component_disabled_by_default():
    client = _client()

    response = client.get("/health")

    # no STRIPE_SECRET_KEY/STRIPE_WEBHOOK_SECRET configured in this environment
    assert response.json()["data"]["components"]["stripe"] == "disabled"
