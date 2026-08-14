from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_loader_contain_fetch_domain():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "/api/v1/branding/domain" in res.text


def test_loader_usa_api_base_configuravel():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "dataset.api" in res.text


def test_loader_suporta_debug_configuravel():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "dataset.debug" in res.text


def test_loader_credentials_omit_preserva_isolamento_cross_origin():
    """The loader runs on arbitrary third-party domains — it must never send
    the embedding page's own cookies to the Nexara API."""
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert 'credentials: "omit"' in res.text
