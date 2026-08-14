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


def test_read_models_v1_retorna_service_names():
    client = _client()

    response = client.get("/api/v1/read-models/v1")

    assert response.status_code == 200
    body = response.json()["data"]
    assert "runtime" in body["service_names"]
    assert len(body["service_names"]) == 13
    assert body["version"] == "1.0.0"


def test_read_models_v2_retorna_service_names():
    client = _client()

    response = client.get("/api/v1/read-models/v2")

    assert response.status_code == 200
    body = response.json()["data"]
    assert "runtime" in body["service_names"]
    assert len(body["service_names"]) == 13


def test_read_models_v1_sem_token_nao_e_rate_limitado():
    client = _client()

    for _ in range(150):
        response = client.get("/api/v1/read-models/v1")
        assert response.status_code == 200


def test_read_models_v1_com_token_bloqueia_apos_limite_de_rate():
    client = _client()
    token = _login(client, "user@test.com")

    for _ in range(99):
        response = client.get(
            "/api/v1/read-models/v1", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    response = client.get(
        "/api/v1/read-models/v1", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 429


def test_compare_read_models_sem_diferenca():
    client = _client()

    response = client.get("/api/v1/read-models/compare")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["same_keys"] is True
    assert body["same_length"] is True
    assert body["differences"] == []
