"""Contract tests for cdn/loader.js's actual dependency: `/branding/domain`.

Sprint 237's own spec named `/branding/public` as the endpoint the loader
calls, but that endpoint resolves its tenant from a Bearer session token
(`get_request_tenant_id`) — an anonymous visitor on a client's own domain
never carries one, so it would always fall back to the default Nexara theme
and never "detect the domain automatically" as the sprint's own stated goal
requires. `/branding/domain` resolves tenant from the Host header instead
(Sprint 233/236), which is the mechanism a domain-embedded, unauthenticated
loader actually needs — so the loader (and this contract) target it instead.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.branding import get_branding_service
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.branding.branding_service import BrandingService


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


def test_loader_endpoint_nao_exige_autenticacao():
    client, _, _ = _client()

    response = client.get("/api/v1/branding/domain")

    assert response.status_code == 200


def test_loader_endpoint_nao_usa_envelope_api_response():
    """The loader reads the body directly (no `.data` unwrap) — confirms the
    contract it actually relies on."""
    client, _, _ = _client()

    body = client.get("/api/v1/branding/domain").json()

    assert "data" not in body


def test_loader_endpoint_css_url_sempre_presente():
    client, _, _ = _client()

    body = client.get("/api/v1/branding/domain").json()

    assert isinstance(body["css_url"], str)
    assert body["css_url"]


def test_loader_endpoint_logo_url_e_opcional_e_none_sem_upload():
    client, _, _ = _client()

    body = client.get("/api/v1/branding/domain").json()

    assert "logo_url" in body
    assert body["logo_url"] is None


def test_loader_endpoint_logo_url_presente_apos_upload():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("cliente.com", org_id)

    client.post(
        "/api/v1/branding/logo",
        files={"file": ("logo.png", b"fake-png-bytes", "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    body = client.get("/api/v1/branding/domain", headers={"host": "cliente.com"}).json()

    assert body["logo_url"] is not None


def test_loader_endpoint_detecta_dominio_automaticamente_via_host():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("cliente.com", org_id)

    body = client.get("/api/v1/branding/domain", headers={"host": "cliente.com"}).json()

    assert body["tenant_id"] == org_id


def test_loader_endpoint_dominio_desconhecido_cai_no_tema_default():
    client, _, _ = _client()

    body = client.get("/api/v1/branding/domain", headers={"host": "never-seen.com"}).json()

    assert body["tenant_id"] is None
    assert body["css_url"]
