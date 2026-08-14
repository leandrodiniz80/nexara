from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.platform_metrics import PlatformMetrics


def _client(metrics=None) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), metrics=metrics)
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app), container


def _login(client: TestClient, email: str, role: str = "user", organization_id=None) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "123456",
            "role": role,
            "organization_id": organization_id,
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_metrics_sem_token_bloqueia():
    client, _ = _client(metrics=PlatformMetrics())

    response = client.get("/api/v1/metrics")

    assert response.status_code == 401


def test_metrics_sem_role_adequada_bloqueia():
    client, _ = _client(metrics=PlatformMetrics())

    owner_token = _login(client, "owner@test.com", role="user")
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    org_id = me_response.json()["data"]["organization_id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "member@test.com",
            "password": "123456",
            "role": "user",
            "organization_id": org_id,
            "organization_role": "member",
        },
    )
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "member@test.com", "password": "123456"}
    )
    member_token = login_response.json()["data"]["token"]

    response = client.get(
        "/api/v1/metrics", headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


def test_metrics_com_role_admin_funciona():
    client, _ = _client(metrics=PlatformMetrics())
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert "metrics" in response.json()["data"]


def test_metrics_com_organization_role_owner_funciona():
    client, _ = _client(metrics=PlatformMetrics())
    # organization_id omitido -> auto-cria org e vira owner automaticamente
    token = _login(client, "owner@test.com", role="user")

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_metrics_retorna_dados_apos_acoes():
    client, _ = _client(metrics=PlatformMetrics())
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})

    data = response.json()["data"]["metrics"]
    assert data["counters"]["auth.register"] >= 1
    assert data["counters"]["auth.login.success"] >= 1
    assert "auth.login.duration" in data["timings"]
    assert data["timings"]["auth.login.duration"]["count"] >= 1


def test_metrics_sem_metrics_configurado_retorna_vazio():
    client, _ = _client(metrics=None)
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"]["metrics"] == {}


def test_metrics_nao_expoe_senha():
    client, _ = _client(metrics=PlatformMetrics())
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})

    assert "123456" not in response.text
