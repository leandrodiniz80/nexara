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


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_org_me_sem_token_bloqueia():
    client = _client()

    response = client.get("/api/v1/org/me")

    assert response.status_code == 401


def test_org_me_retorna_organizacao_auto_criada():
    client = _client()
    token = _login(client, "user@test.com")

    response = client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["organization_id"] is not None
    assert body["user_count"] == 1


def test_org_me_conta_usuarios_da_organizacao():
    client = _client()

    client.post(
        "/api/v1/auth/register", json={"email": "owner@test.com", "password": "123456"}
    )
    me_response = client.post(
        "/api/v1/auth/login", json={"email": "owner@test.com", "password": "123456"}
    )
    owner_token = me_response.json()["data"]["token"]

    org_response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {owner_token}"}
    )
    org_id = org_response.json()["data"]["organization_id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "teammate@test.com",
            "password": "123456",
            "organization_id": org_id,
        },
    )
    teammate_login = client.post(
        "/api/v1/auth/login", json={"email": "teammate@test.com", "password": "123456"}
    )
    teammate_token = teammate_login.json()["data"]["token"]

    response = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {teammate_token}"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["user_count"] == 2
