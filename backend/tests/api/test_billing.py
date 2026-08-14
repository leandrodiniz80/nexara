from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client() -> TestClient:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app)


def _login(client: TestClient, email: str, organization_id: str | None = None) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "organization_id": organization_id},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_get_plan_sem_token_bloqueia():
    client = _client()

    response = client.get("/api/v1/billing/plan")

    assert response.status_code == 401


def test_get_plan_retorna_free_por_padrao():
    client = _client()
    token = _login(client, "owner@test.com")

    response = client.get("/api/v1/billing/plan", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["plan"] == "free"
    assert body["limits"]["users"] == 1


def test_upgrade_owner_funciona():
    client = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    plan_response = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {token}"}
    )
    assert plan_response.json()["data"]["plan"] == "pro"


def test_upgrade_nao_owner_bloqueia():
    client = _client()
    owner_token = _login(client, "owner@test.com")

    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]

    member_token = _login(client, "member@test.com", organization_id=org_id)

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 403


def test_upgrade_plano_invalido_retorna_400():
    client = _client()
    token = _login(client, "owner@test.com")

    response = client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "does-not-exist"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
