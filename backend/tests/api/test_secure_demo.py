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


def _login(client: TestClient, email: str, role: str = "user", permissions=None) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "123456",
            "role": role,
            "permissions": permissions or [],
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_test_auth_sem_token_bloqueia():
    client = _client()

    response = client.get("/api/v1/secure/test-auth")

    assert response.status_code == 401


def test_test_auth_com_token_funciona():
    client = _client()
    token = _login(client, "user@test.com")

    response = client.get("/api/v1/secure/test-auth", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"]["email"] == "user@test.com"


def test_test_auth_bloqueia_apos_limite_de_rate():
    client = _client()
    token = _login(client, "user@test.com")

    for _ in range(99):
        response = client.get(
            "/api/v1/secure/test-auth", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    response = client.get("/api/v1/secure/test-auth", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 429


def test_test_role_bloqueia_role_incorreta():
    client = _client()
    token = _login(client, "user@test.com", role="user")

    response = client.get(
        "/api/v1/secure/test-role",
        params={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_test_role_funciona_com_role_correta():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/secure/test-role",
        params={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"


def test_test_permission_bloqueia_sem_permissao():
    client = _client()
    token = _login(client, "user@test.com", permissions=[])

    response = client.get(
        "/api/v1/secure/test-permission",
        params={"permission": "campaign:create"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_test_permission_funciona_com_permissao():
    client = _client()
    token = _login(client, "user@test.com", permissions=["campaign:create"])

    response = client.get(
        "/api/v1/secure/test-permission",
        params={"permission": "campaign:create"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "campaign:create" in response.json()["data"]["permissions"]
