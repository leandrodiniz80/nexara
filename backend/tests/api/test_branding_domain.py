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


def test_branding_por_dominio_resolve_org_registrada():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    resolver.register_domain("cliente-a.com", org_id)
    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.get("/api/v1/branding/domain", headers={"host": "cliente-a.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["theme"]["colors"]["primary_bg"] == "#FF0000"
    assert body["tenant_id"] == org_id
    assert body["name"] == "Nexara"


def test_branding_por_dominio_nao_usa_envelope_api_response():
    client, _, _ = _client()

    body = client.get("/api/v1/branding/domain").json()

    assert "data" not in body
    assert body["name"] == "Nexara"


def test_dominio_nao_registrado_cai_no_padrao_nexara():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/domain", headers={"host": "unknown-domain.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] is None
    assert body["theme"]["colors"]["primary_bg"] == "#0B0F1A"


def test_dois_dominios_isolados():
    client, container, resolver = _client()
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")

    resolver.register_domain("cliente-a.com", org_a)
    resolver.register_domain("cliente-b.com", org_b)
    client.post(
        "/api/v1/branding/custom",
        json=_THEME_RED,
        headers={"Authorization": f"Bearer {token_a}"},
    )

    response_a = client.get("/api/v1/branding/domain", headers={"host": "cliente-a.com"})
    response_b = client.get("/api/v1/branding/domain", headers={"host": "cliente-b.com"})

    assert response_a.json()["theme"]["colors"]["primary_bg"] == "#FF0000"
    assert response_b.json()["theme"]["colors"]["primary_bg"] == "#0B0F1A"


def test_dominio_com_porta_e_normalizado():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("cliente-a.com", org_id)
    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.get("/api/v1/branding/domain", headers={"host": "cliente-a.com:8443"})

    assert response.json()["theme"]["colors"]["primary_bg"] == "#FF0000"


def test_dominio_case_insensitive():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("Cliente-A.com", org_id)
    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.get("/api/v1/branding/domain", headers={"host": "cliente-a.com"})

    assert response.json()["theme"]["colors"]["primary_bg"] == "#FF0000"


def test_resolver_isolado_entre_testes():
    """Confirms DomainTenantResolver is properly overridable per test — a bare
    module-level dict (as originally proposed) would leak domain
    registrations across the whole test session with no way to reset them.
    """
    client, _, resolver = _client()

    assert resolver.resolve("cliente-a.com") is None
