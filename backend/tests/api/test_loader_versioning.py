from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_loader_latest_existe():
    client = _client()

    res = client.get("/api/v1/cdn/loader")

    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]


def test_loader_latest_nao_e_immutable():
    client = _client()

    res = client.get("/api/v1/cdn/loader")

    assert "immutable" not in res.headers.get("Cache-Control", "")


def test_loader_latest_e_no_cache():
    client = _client()

    res = client.get("/api/v1/cdn/loader")

    assert res.headers["cache-control"] == "no-cache"


def test_loader_v1_continua_immutable():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "immutable" in res.headers["Cache-Control"]


def test_loader_v1_headers_inalterados_pelo_registry():
    """The refactor into a version registry must not change /loader.v1.js's
    established Sprint 239 contract — same Cache-Control, still ETag/Vary,
    still gzip-negotiated."""
    client = _client()

    res = client.get(
        "/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "identity"}
    )

    assert res.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "ETag" in res.headers
    assert res.headers["vary"] == "Accept-Encoding"
    assert res.headers.get("content-encoding") is None


def test_loader_latest_e_v1_servem_o_mesmo_conteudo_hoje():
    """_CURRENT_VERSION == "v1" today — /loader and /loader.v1.js must agree
    until a v2 is actually rolled out."""
    client = _client()

    latest = client.get(
        "/api/v1/cdn/loader", headers={"Accept-Encoding": "identity"}
    ).content
    pinned = client.get(
        "/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "identity"}
    ).content

    assert latest == pinned


def test_loader_latest_suporta_gzip():
    client = _client()

    res = client.get("/api/v1/cdn/loader", headers={"Accept-Encoding": "gzip"})

    assert res.headers.get("Content-Encoding") == "gzip"
