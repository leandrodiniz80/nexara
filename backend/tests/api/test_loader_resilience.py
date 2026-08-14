"""Contract tests for the Sprint 240 resilience additions to cdn/loader.v1.js
(timeout, retry-with-backoff, and the DOMContentLoaded guard that this
sprint's own rewrite would otherwise have dropped — see cdn/loader.v1.js's
`init()` and the bottom-of-file readyState check).
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_endpoint_domain_responde_normal():
    client = _client()

    res = client.get("/api/v1/branding/domain")

    assert res.status_code in (200, 404)


def test_loader_endpoint_nao_quebra():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]


def test_loader_usa_abort_controller_para_timeout():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "AbortController" in res.text


def test_loader_tem_logica_de_retry():
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert "RETRIES" in res.text
    assert "attemptFetchTheme" in res.text


def test_loader_preserva_guarda_de_dom_content_loaded():
    """This is the regression this sprint's own spec introduced: rewriting
    the file from scratch dropped the `readyState === "loading"` guard,
    calling `init()` unconditionally. Without it, a script placed in <head>
    without defer/async runs before `document.body` exists, and
    `document.body.prepend(img)` in `applyTheme()` throws — silently
    swallowed, but the logo/theme never applies and the fetched theme never
    gets cached for next load. The guard must survive every rewrite.
    """
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert 'document.readyState === "loading"' in res.text
    assert "DOMContentLoaded" in res.text


def test_loader_nunca_lanca_erro_nao_tratado_no_fluxo_de_init():
    """init() must catch a total fetch failure (API down through every
    retry) rather than let it become an unhandled promise rejection that
    would abort the rest of the script."""
    client = _client()

    res = client.get("/api/v1/cdn/loader.v1.js")

    assert ".catch(function (err) {" in res.text
