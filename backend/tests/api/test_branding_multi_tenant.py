from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.branding import get_branding_service
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.branding.branding_service import BrandingService

_VALID_THEME_PAYLOAD = {
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


def _client() -> tuple[TestClient, PlatformContainer, BrandingService]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    branding_service = BrandingService()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_branding_service] = lambda: branding_service
    return TestClient(app), container, branding_service


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_branding_publico_continua_funcionando_sem_autenticacao():
    client, _, _ = _client()

    response = client.get("/api/v1/branding")

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Nexara"
    assert response.json()["data"]["theme"]["colors"]["primary_bg"] == "#0B0F1A"


def test_tenant_sem_branding_customizado_recebe_nexara_default():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.get("/api/v1/branding", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"]["theme"]["colors"]["primary_bg"] == "#0B0F1A"


def test_owner_pode_customizar_branding_do_proprio_tenant():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/custom",
        json=_VALID_THEME_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["theme"]["colors"]["primary_bg"] == "#FF0000"


def test_branding_isolado_entre_tenants():
    client, _, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")

    client.post(
        "/api/v1/branding/custom",
        json=_VALID_THEME_PAYLOAD,
        headers={"Authorization": f"Bearer {token_a}"},
    )

    response_a = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token_a}"}
    )
    response_b = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response_a.json()["data"]["theme"]["colors"]["primary_bg"] == "#FF0000"
    assert response_b.json()["data"]["theme"]["colors"]["primary_bg"] == "#0B0F1A"


def test_customizacao_de_um_tenant_persiste_entre_chamadas():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.post(
        "/api/v1/branding/custom",
        json=_VALID_THEME_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    first = client.get("/api/v1/branding", headers={"Authorization": f"Bearer {token}"})
    second = client.get("/api/v1/branding", headers={"Authorization": f"Bearer {token}"})

    assert first.json()["data"]["theme"] == second.json()["data"]["theme"]


def test_membro_nao_owner_nao_pode_customizar_branding():
    client, container, _ = _client()
    owner_token = _login(client, "owner@test.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    org_id = me.json()["data"]["organization_id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "member@test.com",
            "password": "123456",
            "organization_id": org_id,
            "organization_role": "member",
        },
    )
    member_token = _login(client, "member@test.com")

    response = client.post(
        "/api/v1/branding/custom",
        json=_VALID_THEME_PAYLOAD,
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 403


def test_custom_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    response = client.post("/api/v1/branding/custom", json=_VALID_THEME_PAYLOAD)

    assert response.status_code == 401


def test_custom_com_payload_invalido_retorna_422():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/custom",
        json={"colors": {"primary_bg": "#FF0000"}},  # missing required fields
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_branding_service_e_isolado_por_teste_via_override():
    """Confirms `get_branding_service` is properly overridable per test (via
    `dependency_overrides`), so custom themes set in one test never leak into
    another — the shared module-level singleton is production-only.
    """
    client, _, branding_service = _client()
    token = _login(client, "owner@test.com")

    client.post(
        "/api/v1/branding/custom",
        json=_VALID_THEME_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me.json()["data"]["organization_id"]
    assert len(branding_service.get_versions(org_id)) == 1
