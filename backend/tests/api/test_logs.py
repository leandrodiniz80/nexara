from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.logging.platform_logger import PlatformLogger


def _client(logger=None) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), logger=logger)
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


def test_logs_sem_token_bloqueia():
    client, _ = _client(logger=PlatformLogger())

    response = client.get("/api/v1/logs")

    assert response.status_code == 401


def test_logs_sem_role_adequada_bloqueia():
    client, _ = _client(logger=PlatformLogger())

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

    response = client.get("/api/v1/logs", headers={"Authorization": f"Bearer {member_token}"})

    assert response.status_code == 403


def test_logs_com_role_admin_funciona():
    client, _ = _client(logger=PlatformLogger())
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    logs = response.json()["data"]
    assert isinstance(logs, list)
    assert any(entry["message"] == "auth.register" for entry in logs)


def test_logs_sem_logger_configurado_retorna_vazio():
    client, _ = _client(logger=None)
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_logs_filtro_por_level():
    client, _ = _client(logger=PlatformLogger())
    token = _login(client, "admin@test.com", role="admin")
    client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "wrong"})

    response = client.get(
        "/api/v1/logs", params={"level": "WARN"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    logs = response.json()["data"]
    assert len(logs) >= 1
    assert all(entry["level"] == "WARN" for entry in logs)
    assert any(entry["message"] == "auth.login.failed" for entry in logs)


def test_logs_respeita_limit():
    client, _ = _client(logger=PlatformLogger())
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/logs", params={"limit": 1}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_logs_nao_expoe_senha():
    client, _ = _client(logger=PlatformLogger())
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/logs", headers={"Authorization": f"Bearer {token}"})

    assert "123456" not in response.text


def test_correlation_id_e_reutilizado_do_header_do_cliente():
    client, _ = _client(logger=None)

    response = client.get("/health", headers={"X-Correlation-ID": "client-supplied-id"})

    assert response.headers["X-Correlation-ID"] == "client-supplied-id"


def test_correlation_id_e_gerado_quando_ausente():
    client, _ = _client(logger=None)

    response = client.get("/health")

    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0


def test_correlation_id_propaga_ate_o_log_de_login():
    logger = PlatformLogger()
    client, container = _client(logger=logger)
    client.post(
        "/api/v1/auth/register", json={"email": "user@test.com", "password": "123456"}
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.com", "password": "123456"},
        headers={"X-Correlation-ID": "trace-me-123"},
    )

    assert response.headers["X-Correlation-ID"] == "trace-me-123"

    login_logs = [e for e in logger.get_logs() if e["message"] == "auth.login.success"]
    assert len(login_logs) == 1
    assert login_logs[0]["correlation_id"] == "trace-me-123"


def test_tracing_registra_http_request_com_tempo_path_e_status():
    logger = PlatformLogger()
    client, container = _client(logger=logger)

    response = client.get("/health")

    assert response.status_code == 200

    trace_logs = [e for e in logger.get_logs() if e["message"] == "http.request"]
    assert len(trace_logs) == 1
    entry = trace_logs[0]
    assert entry["level"] == "INFO"
    assert entry["metadata"]["path"] == "/health"
    assert entry["metadata"]["status"] == 200
    assert entry["metadata"]["duration"] >= 0


def test_tracing_sem_logger_nao_quebra():
    client, _ = _client(logger=None)

    response = client.get("/health")

    assert response.status_code == 200
