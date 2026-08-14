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
    branding_service = BrandingService(audit=container.audit)
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_branding_service] = lambda: branding_service
    return TestClient(app), container, branding_service


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def _upload_logo(client: TestClient, token: str) -> None:
    client.post(
        "/api/v1/branding/logo",
        files={"file": ("logo.png", _PNG_BYTES, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_get_logo_organizacao_sem_logo_retorna_404():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/logo/org-ghost")

    assert response.status_code == 404


def test_get_logo_publica_sem_autenticacao():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me.json()["data"]["organization_id"]
    _upload_logo(client, token)

    response = client.get(f"/api/v1/branding/logo/{org_id}")  # no Authorization header at all

    assert response.status_code == 200
    assert response.content == _PNG_BYTES


def test_get_logo_retorna_content_type_correto():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me.json()["data"]["organization_id"]
    _upload_logo(client, token)

    response = client.get(f"/api/v1/branding/logo/{org_id}")

    assert response.headers["content-type"] == "image/png"


def test_get_logo_tem_cache_control_imutavel():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me.json()["data"]["organization_id"]
    _upload_logo(client, token)

    response = client.get(f"/api/v1/branding/logo/{org_id}")

    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_get_logo_isolado_por_tenant():
    client, _, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    me_a = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    org_a = me_a.json()["data"]["organization_id"]
    _upload_logo(client, token_a)

    response_b = client.get("/api/v1/branding/logo/org-b-never-uploaded")

    assert client.get(f"/api/v1/branding/logo/{org_a}").status_code == 200
    assert response_b.status_code == 404


def test_branding_response_logo_url_none_sem_upload():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["data"]["logo_url"] is None


def test_branding_response_logo_url_apos_upload():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    _upload_logo(client, token)

    response = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token}"}
    )

    logo_url = response.json()["data"]["logo_url"]
    assert logo_url is not None
    assert client.get(logo_url).status_code == 200


def test_public_branding_logo_url_apos_upload():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    _upload_logo(client, token)

    response = client.get(
        "/api/v1/branding/public", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["logo_url"] is not None


def test_domain_branding_logo_url_apos_upload():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    _upload_logo(client, token)

    response = client.get(
        "/api/v1/branding/domain", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.json()["logo_url"] is not None


def test_logo_url_isolado_por_tenant_nas_respostas_de_branding():
    client, _, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")
    _upload_logo(client, token_a)

    data_a = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]
    data_b = client.get(
        "/api/v1/branding", headers={"Authorization": f"Bearer {token_b}"}
    ).json()["data"]

    assert data_a["logo_url"] is not None
    assert data_b["logo_url"] is None
