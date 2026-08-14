import gzip

from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_loader_sem_gzip():
    client = _client()

    # httpx (the TestClient's underlying HTTP client) sends
    # "Accept-Encoding: gzip, deflate, br" by default on every request —
    # relying on that default being absent would make this test flaky/wrong.
    # "identity" explicitly simulates a client that does not accept any
    # content-coding, which is the actual scenario under test.
    res = client.get(
        "/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "identity"}
    )

    assert res.status_code == 200
    assert res.headers.get("Content-Encoding") is None
    assert "Cache-Control" in res.headers
    assert "ETag" in res.headers


def test_loader_com_gzip():
    client = _client()

    res = client.get(
        "/api/v1/cdn/loader.v1.js",
        headers={"Accept-Encoding": "gzip"},
    )

    assert res.status_code == 200
    assert res.headers.get("Content-Encoding") == "gzip"
    assert res.headers.get("Vary") == "Accept-Encoding"


def test_etag_muda_com_encoding():
    client = _client()

    res1 = client.get("/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "identity"})
    res2 = client.get("/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "gzip"})

    assert res1.headers["ETag"] != res2.headers["ETag"]


def test_etag_estavel_para_o_mesmo_encoding():
    client = _client()

    res1 = client.get("/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "gzip"})
    res2 = client.get("/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "gzip"})

    assert res1.headers["ETag"] == res2.headers["ETag"]


def test_conteudo_gzip_descomprime_para_o_mesmo_loader():
    client = _client()

    raw = client.get(
        "/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "identity"}
    ).content
    gzipped_response = client.get(
        "/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "gzip"}
    )

    # httpx transparently decodes "Content-Encoding: gzip" when reading
    # `.content` (same behavior a real browser has) — read the raw wire
    # bytes via `.read()` on the underlying stream is not exposed here, so
    # this instead confirms the decoded body still matches byte-for-byte,
    # proving compression didn't corrupt the payload.
    assert gzipped_response.content == raw


def test_vary_presente_mesmo_sem_gzip():
    client = _client()

    res = client.get(
        "/api/v1/cdn/loader.v1.js", headers={"Accept-Encoding": "identity"}
    )

    assert res.headers.get("Vary") == "Accept-Encoding"
