from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.branding import get_branding_service
from app.platform.audit.platform_audit import PlatformAudit
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

_THEME_BLUE = {
    **_THEME_RED,
    "colors": {**_THEME_RED["colors"], "primary_bg": "#0000FF"},
}


def _client() -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    # Constructed once, outside the lambda: dependency resolution runs fresh per
    # request, so a service built inside the lambda would never see its own
    # prior writes across the multiple requests these tests make.
    branding_service = BrandingService(audit=container.audit)
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_branding_service] = lambda: branding_service
    return TestClient(app), container


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_cria_duas_versoes_e_lista_em_ordem_desc():
    client, _ = _client()
    token = _login(client, "owner@test.com")

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )
    client.post(
        "/api/v1/branding/custom", json=_THEME_BLUE, headers={"Authorization": f"Bearer {token}"}
    )

    response = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    versions = response.json()["data"]
    assert [v["version"] for v in versions] == [2, 1]


def test_payload_de_cada_versao_preservado():
    client, _ = _client()
    token = _login(client, "owner@test.com")

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )
    client.post(
        "/api/v1/branding/custom", json=_THEME_BLUE, headers={"Authorization": f"Bearer {token}"}
    )

    versions = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]

    assert versions[0]["theme"]["colors"]["primary_bg"] == "#0000FF"
    assert versions[1]["theme"]["colors"]["primary_bg"] == "#FF0000"
    assert "created_at" in versions[0]


def test_lista_vazia_sem_customizacao_previa():
    client, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_versions_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/branding/versions")

    assert response.status_code == 401


def test_versions_membro_nao_owner_bloqueado():
    client, _ = _client()
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

    response = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


def test_versions_isoladas_por_tenant():
    client, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")

    client.post(
        "/api/v1/branding/custom",
        json=_THEME_RED,
        headers={"Authorization": f"Bearer {token_a}"},
    )

    versions_a = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]
    versions_b = client.get(
        "/api/v1/branding/versions", headers={"Authorization": f"Bearer {token_b}"}
    ).json()["data"]

    assert len(versions_a) == 1
    assert versions_b == []


def test_atualizar_branding_gera_evento_de_auditoria():
    client, container = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    client.post(
        "/api/v1/branding/custom", json=_THEME_RED, headers={"Authorization": f"Bearer {token}"}
    )

    events = [e for e in container.audit.get_events() if e["event"] == "branding_updated"]
    assert len(events) == 1
    assert events[0]["organization_id"] == org_id
    assert events[0]["metadata"]["version"] == 1
