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


def test_register_cria_usuario():
    client = _client()

    response = client.post(
        "/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"}
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_register_duplicado_retorna_409():
    client = _client()

    client.post("/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"})
    response = client.post(
        "/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"}
    )

    assert response.status_code == 409


def test_login_retorna_token():
    client = _client()
    client.post("/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"})

    response = client.post(
        "/api/v1/auth/login", json={"email": "user@test.com", "password": "123456"}
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["email"] == "user@test.com"
    assert "token" in body


def test_login_credenciais_invalidas_retorna_401():
    client = _client()
    client.post("/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"})

    response = client.post(
        "/api/v1/auth/login", json={"email": "user@test.com", "password": "wrong"}
    )

    assert response.status_code == 401


def test_login_usuario_inexistente_retorna_401():
    client = _client()

    response = client.post(
        "/api/v1/auth/login", json={"email": "ghost@test.com", "password": "whatever"}
    )

    assert response.status_code == 401


def test_me_sem_token_retorna_401():
    client = _client()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_com_token_retorna_usuario():
    client = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.com", "password": "123456", "role": "admin"},
    )
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "admin@test.com", "password": "123456"}
    )
    token = login_response.json()["data"]["token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["email"] == "admin@test.com"
    assert body["role"] == "admin"
    assert body["organization_id"] is not None


def test_me_com_token_invalido_retorna_401():
    client = _client()

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401


def test_login_bloqueia_apos_limite_de_rate_do_plano_free():
    client = _client()
    client.post("/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"})

    for _ in range(100):
        response = client.post(
            "/api/v1/auth/login", json={"email": "user@test.com", "password": "123456"}
        )
        assert response.status_code == 200

    response = client.post(
        "/api/v1/auth/login", json={"email": "user@test.com", "password": "123456"}
    )

    assert response.status_code == 429


def test_logout_invalida_token():
    client = _client()
    client.post("/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"})
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "user@test.com", "password": "123456"}
    )
    token = login_response.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200

    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 401


# --- Sprint 254: self-registration can no longer self-escalate to admin
# once an admin already exists on the platform -------------------------


def test_primeiro_admin_do_sistema_pode_se_auto_registrar():
    """Bootstrap case: no admin exists yet, so registering with
    role="admin" directly (no Bearer token) is still allowed — otherwise
    no admin could ever be created at all."""
    client = _client()

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "first-admin@test.com", "password": "123456", "role": "admin"},
    )

    assert response.status_code == 200


def test_segundo_admin_nao_pode_se_auto_registrar_sem_token():
    """The actual security fix: once an admin exists, an anonymous caller
    can no longer grant themselves admin just by setting role="admin" on
    a public, unauthenticated registration request."""
    client = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "first-admin@test.com", "password": "123456", "role": "admin"},
    )

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@test.com", "password": "123456", "role": "admin"},
    )

    assert response.status_code == 403


def test_admin_existente_pode_criar_outro_admin():
    client = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "first-admin@test.com", "password": "123456", "role": "admin"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "first-admin@test.com", "password": "123456"}
    )
    admin_token = login.json()["data"]["token"]

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "second-admin@test.com", "password": "123456", "role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


def test_usuario_comum_autenticado_nao_pode_criar_admin():
    client = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "first-admin@test.com", "password": "123456", "role": "admin"},
    )
    client.post(
        "/api/v1/auth/register", json={"email": "regular@test.com", "password": "123456"}
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "regular@test.com", "password": "123456"}
    )
    user_token = login.json()["data"]["token"]

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "attacker@test.com", "password": "123456", "role": "admin"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 403


def test_registro_de_usuario_comum_nao_e_afetado_pela_restricao_de_admin():
    """The restriction only applies to role="admin" — registering as a
    plain user always works, admin or not, token or not."""
    client = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "first-admin@test.com", "password": "123456", "role": "admin"},
    )

    response = client.post(
        "/api/v1/auth/register", json={"email": "anyone@test.com", "password": "123456"}
    )

    assert response.status_code == 200
