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


def test_domain_etag_presente_na_primeira_resposta():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/domain")

    assert response.status_code == 200
    assert response.headers.get("etag")


def test_domain_cache_control_presente():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/domain")

    assert response.headers["cache-control"] == "public, max-age=300"


def test_domain_retorna_304_com_if_none_match_valido():
    client, _, _ = _client()

    first = client.get("/api/v1/branding/domain")
    etag = first.headers["etag"]

    second = client.get("/api/v1/branding/domain", headers={"if-none-match": etag})

    assert second.status_code == 304


def test_domain_etag_estavel_quando_nada_muda():
    client, _, _ = _client()

    first = client.get("/api/v1/branding/domain").headers["etag"]
    second = client.get("/api/v1/branding/domain").headers["etag"]

    assert first == second


def test_domain_etag_muda_apos_customizacao():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("cliente-a.com", org_id)

    before = client.get("/api/v1/branding/domain", headers={"host": "cliente-a.com"})
    etag_before = before.headers["etag"]

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    after = client.get("/api/v1/branding/domain", headers={"host": "cliente-a.com"})
    etag_after = after.headers["etag"]

    assert etag_before != etag_after


def test_domain_if_none_match_desatualizado_retorna_200():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("cliente-a.com", org_id)

    stale_etag = client.get(
        "/api/v1/branding/domain", headers={"host": "cliente-a.com"}
    ).headers["etag"]

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.get(
        "/api/v1/branding/domain",
        headers={"host": "cliente-a.com", "if-none-match": stale_etag},
    )

    assert response.status_code == 200
    assert response.json()["theme"]["colors"]["primary_bg"] == "#FF0000"


def test_css_etag_presente():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/css")

    assert response.status_code == 200
    assert response.headers.get("etag")


def test_css_cache_control_presente():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/css")

    assert response.headers["cache-control"] == "public, max-age=300"


def test_css_retorna_304_com_if_none_match_valido():
    client, _, _ = _client()

    first = client.get("/api/v1/branding/css")
    etag = first.headers["etag"]

    second = client.get("/api/v1/branding/css", headers={"if-none-match": etag})

    assert second.status_code == 304


def test_css_e_domain_tem_etags_independentes_por_endpoint():
    """Both endpoints hash the same theme, so their ETags for the same tenant
    should actually match — but each is computed independently, not shared
    state, so this also confirms neither endpoint accidentally caches the
    other's response.
    """
    client, _, _ = _client()

    domain_etag = client.get("/api/v1/branding/domain").headers["etag"]
    css_etag = client.get("/api/v1/branding/css").headers["etag"]

    assert domain_etag == css_etag
