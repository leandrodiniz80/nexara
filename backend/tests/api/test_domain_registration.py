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


def test_register_domain_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    response = client.post("/api/v1/branding/domain/register", json={"domain": "cliente.com"})

    assert response.status_code == 401


def test_owner_registra_dominio_com_sucesso():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    response = client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["domain"] == "cliente.com"
    assert body["data"]["organization_id"] == org_id
    assert resolver.get_owner("cliente.com") == org_id


def test_membro_nao_owner_bloqueado():
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
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 403


def test_dominio_registrado_resolve_imediatamente_via_branding_domain():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get("/api/v1/branding/domain", headers={"host": "cliente.com"})

    assert response.json()["tenant_id"] is not None


def test_dominio_ja_registrado_por_outra_organizacao_retorna_409():
    client, _, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")

    client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    response = client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 409


def test_reregistrar_o_mesmo_dominio_pela_mesma_organizacao_e_idempotente():
    client, container, _ = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    first = client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    second = client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "cliente.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["organization_id"] == org_id


def test_dominio_e_normalizado_para_minusculas():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")

    client.post(
        "/api/v1/branding/domain/register",
        json={"domain": "Cliente.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resolver.get_owner("cliente.com") == org_id


def test_payload_sem_domain_retorna_422():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/branding/domain/register",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
