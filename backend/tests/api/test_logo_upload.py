from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.branding import get_branding_service
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.branding.branding_service import BrandingService

_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00fake-png-content"


def _client() -> tuple[TestClient, PlatformContainer, BrandingService]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    # Constructed once, outside the lambda: dependency resolution runs fresh per
    # request, so a service built inside the lambda would never see its own
    # prior writes across the multiple requests these tests make.
    branding_service = BrandingService(audit=container.audit)
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_branding_service] = lambda: branding_service
    return TestClient(app), container, branding_service


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_upload_logo_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    response = client.post(
        "/api/v1/branding/logo", files={"file": ("logo.png", _PNG_BYTES, "image/png")}
    )

    assert response.status_code == 401


def test_upload_logo_owner_retorna_200_com_logo_url():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/logo",
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    logo_url = response.json()["data"]["logo_url"]
    assert logo_url.startswith("/api/v1/branding/logo/")


def test_upload_logo_membro_nao_owner_bloqueado():
    client, _, _ = _client()
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
        "/api/v1/branding/logo",
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 403


def test_upload_logo_content_type_invalido_retorna_400():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/logo",
        files={"file": ("virus.exe", b"not-an-image", "application/x-msdownload")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_upload_logo_svg_e_aceito():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/logo",
        files={"file": ("logo.svg", b"<svg></svg>", "image/svg+xml")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_upload_logo_persiste_no_branding_service():
    client, _, branding_service = _client()
    token = _login(client, "owner@test.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me.json()["data"]["organization_id"]

    client.post(
        "/api/v1/branding/logo",
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert branding_service.get_logo(org_id) == (_PNG_BYTES, "image/png")


def test_upload_logo_gera_evento_de_auditoria():
    client, container, _ = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    client.post(
        "/api/v1/branding/logo",
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    events = [e for e in container.audit.get_events() if e["event"] == "logo_updated"]
    assert len(events) == 1
    assert events[0]["organization_id"] == org_id
