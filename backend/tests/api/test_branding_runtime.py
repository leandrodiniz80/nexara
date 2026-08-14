from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.branding import get_branding_service
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
        "mono_family": "Fira Code, monospace",
    },
    "spacing": {"xs": 2, "sm": 4, "md": 8, "lg": 12, "xl": 20},
    "layout": {
        "border_radius": 4,
        "shadow_sm": "none",
        "shadow_md": "none",
        "shadow_lg": "none",
    },
}


def _client() -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    branding_service = BrandingService()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_branding_service] = lambda: branding_service
    return TestClient(app), container


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_public_branding_sem_auth():
    client, _ = _client()

    response = client.get("/api/v1/branding/public")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Nexara"
    assert "colors" in data
    assert "typography" in data
    assert "layout" in data


def test_public_branding_nao_usa_envelope_api_response():
    client, _ = _client()

    body = client.get("/api/v1/branding/public").json()

    # deliberately NOT the ApiResponse envelope — "name" at the top level,
    # not nested under "data".
    assert "data" not in body
    assert body["name"] == "Nexara"


def test_css_endpoint():
    client, _ = _client()

    response = client.get("/api/v1/branding/css")

    assert response.status_code == 200
    css = response.text

    assert ":root" in css
    assert "--color-primary-bg" in css
    assert "--color-accent-primary" in css
    assert "--font-family" in css
    assert "--font-mono" in css
    assert "--radius" in css
    assert "--shadow-sm" in css
    assert "--space-md" in css


def test_css_endpoint_content_type_e_texto_plano():
    client, _ = _client()

    response = client.get("/api/v1/branding/css")

    assert response.headers["content-type"].startswith("text/plain")


def test_public_e_css_refletem_branding_customizado_do_tenant():
    client, _ = _client()
    token = _login(client, "owner@test.com")

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    public = client.get(
        "/api/v1/branding/public", headers={"Authorization": f"Bearer {token}"}
    ).json()
    css = client.get(
        "/api/v1/branding/css", headers={"Authorization": f"Bearer {token}"}
    ).text

    assert public["colors"]["primary_bg"] == "#FF0000"
    assert "#FF0000" in css


def test_public_e_css_isolados_por_tenant():
    client, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")

    client.post(
        "/api/v1/branding/custom",
        json=_THEME_RED,
        headers={"Authorization": f"Bearer {token_a}"},
    )

    public_a = client.get(
        "/api/v1/branding/public", headers={"Authorization": f"Bearer {token_a}"}
    ).json()
    public_b = client.get(
        "/api/v1/branding/public", headers={"Authorization": f"Bearer {token_b}"}
    ).json()

    assert public_a["colors"]["primary_bg"] == "#FF0000"
    assert public_b["colors"]["primary_bg"] == "#0B0F1A"


def test_branding_get_inclui_layout():
    client, _ = _client()

    response = client.get("/api/v1/branding")

    theme = response.json()["data"]["theme"]
    assert "layout" in theme
    assert theme["layout"]["border_radius"] == 8


def test_custom_branding_com_layout_customizado():
    client, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    theme = response.json()["data"]["theme"]
    assert theme["layout"]["border_radius"] == 4
    assert theme["typography"]["mono_family"] == "Fira Code, monospace"


def test_custom_branding_sem_layout_usa_padrao():
    """layout is optional in the request — omitting it falls back to
    DesignTokens' own default layout, not a validation error."""
    client, _ = _client()
    token = _login(client, "owner@test.com")
    payload = {k: v for k, v in _THEME_RED.items() if k != "layout"}
    payload["typography"] = {
        k: v for k, v in _THEME_RED["typography"].items() if k != "mono_family"
    }

    response = client.post(
        "/api/v1/branding/custom", json=payload, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    theme = response.json()["data"]["theme"]
    assert theme["layout"]["border_radius"] == 8
    assert theme["typography"]["mono_family"] == "JetBrains Mono, monospace"
