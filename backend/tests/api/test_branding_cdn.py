from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.branding import get_branding_service
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.branding.branding_service import BrandingService

_THEME_RED = {
    "colors": {
        "primary_bg": "#FF0000",
        "secondary_bg": "#CC0000",
        "border": "#990000",
        "text_primary": "#FFFFFF",
        "text_secondary": "#EEEEEE",
        "text_muted": "#CCCCCC",
        "accent_primary": "#00FF00",
        "accent_success": "#00CC00",
        "accent_warning": "#FFAA00",
        "accent_danger": "#FF0000",
        "accent_info": "#0000FF",
        "gradient_main": "linear-gradient(135deg, #FF0000, #990000)",
    },
    "typography": {
        "font_family": "Roboto, sans-serif",
        "font_size_base": 16,
        "font_weight_regular": 400,
        "font_weight_bold": 700,
    },
    "spacing": {"xs": 2, "sm": 4, "md": 8, "lg": 12, "xl": 20},
}


def _client() -> tuple[TestClient, PlatformContainer, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    branding_service = BrandingService()
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_branding_service] = lambda: branding_service
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container, resolver


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_branding_response_inclui_css_url():
    client, _, _ = _client()

    response = client.get("/api/v1/branding")

    css_url = response.json()["data"]["css_url"]
    assert css_url.startswith("/api/v1/branding/css/")


def test_public_branding_inclui_css_url():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/public")

    assert response.json()["css_url"].startswith("/api/v1/branding/css/")


def test_domain_branding_inclui_css_url():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/domain")

    assert response.json()["css_url"].startswith("/api/v1/branding/css/")


def test_seguir_css_url_retorna_css_valido():
    client, _, _ = _client()

    css_url = client.get("/api/v1/branding").json()["data"]["css_url"]

    response = client.get(css_url)

    assert response.status_code == 200
    assert ":root" in response.text
    assert "--color-primary-bg" in response.text


def test_css_por_hash_e_publico_sem_autenticacao():
    """The whole point of Sprint 234: a hash-versioned URL must be servable
    to a caller with no bearer token at all — a real CDN edge node or an
    anonymous <link> tag never sends one.
    """
    client, container, _ = _client()
    token = _login(client, "owner@test.com")

    css_url = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]["css_url"]

    response = client.get(css_url)  # no Authorization header at all

    assert response.status_code == 200
    assert ":root" in response.text


def test_css_por_hash_tem_cache_control_imutavel():
    client, _, _ = _client()

    css_url = client.get("/api/v1/branding").json()["data"]["css_url"]

    response = client.get(css_url)

    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_css_por_hash_inexistente_retorna_404():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/css/this-hash-was-never-computed")

    assert response.status_code == 404


def test_css_url_estavel_quando_tema_nao_muda():
    client, _, _ = _client()

    url1 = client.get("/api/v1/branding").json()["data"]["css_url"]
    url2 = client.get("/api/v1/branding").json()["data"]["css_url"]

    assert url1 == url2


def test_css_url_muda_apos_customizacao():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    before = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]["css_url"]

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    after = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]["css_url"]

    assert before != after

    response = client.get(after)
    assert "#FF0000" in response.text


def test_css_url_isolada_por_tenant():
    client, container, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")

    client.post(
        "/api/v1/branding/custom",
        json=_THEME_RED,
        headers={"Authorization": f"Bearer {token_a}"},
    )

    url_a = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]["css_url"]
    url_b = client.get("/api/v1/branding/public").json()["css_url"]  # anonymous -> default

    assert url_a != url_b
    assert "#FF0000" in client.get(url_a).text
    assert "#FF0000" not in client.get(url_b).text


def test_hash_antigo_deixa_de_ser_servivel_apos_qualquer_atualizacao():
    """Known, documented limitation of the "clear the whole CSS cache on any
    update" simplification: the old immutable URL 404s once the in-process
    cache is cleared. A real CDN that already cached the (immutable) response
    never re-requests it, so this only affects direct/uncached clients —
    acceptable for this sprint's explicitly in-memory, "evolves later" scope.
    """
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    old_url = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]["css_url"]

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    assert client.get(old_url).status_code == 404
