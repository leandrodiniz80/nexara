from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_loader_js_disponivel():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert res.status_code == 200
    assert "application/javascript" in res.headers["content-type"]


def test_loader_cache_headers():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "cache-control" in res.headers
    assert "immutable" in res.headers["cache-control"]


def test_loader_cache_e_publico_e_um_ano():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert res.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_loader_nao_exige_autenticacao():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert res.status_code == 200


def test_loader_v0_path_nao_existe():
    """Confirms the version is part of the URL, not a query param or header —
    an old, unversioned path must not silently resolve to the same file."""
    client = _client()

    res = client.get("/api/v1/cdn/loader.js")

    assert res.status_code == 404
