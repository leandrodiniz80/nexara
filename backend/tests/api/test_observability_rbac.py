from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.logging.platform_logger import PlatformLogger
from app.platform.metrics.platform_metrics import PlatformMetrics


def _client() -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(
        bootstrap=PlatformBootstrap(),
        audit=PlatformAudit(),
        metrics=PlatformMetrics(),
        logger=PlatformLogger(),
    )
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app), container


def _login(client: TestClient, email: str, password: str = "123456") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["data"]["token"]


def _setup_owner_and_non_owner_admin(client: TestClient) -> tuple[str, str, str]:
    """Owner registers first (auto-creates + owns their org). A second user then
    joins that SAME org as `role="admin"` but `organization_role="member"` —
    the exact scenario the new restriction needs to distinguish from ownership.
    """
    client.post(
        "/api/v1/auth/register", json={"email": "owner@test.com", "password": "123456"}
    )
    owner_token = _login(client, "owner@test.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    org_id = me.json()["data"]["organization_id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@test.com",
            "password": "123456",
            "role": "admin",
            "organization_id": org_id,
            "organization_role": "member",
        },
    )
    admin_token = _login(client, "admin@test.com")

    return owner_token, admin_token, org_id


def _register_member(client: TestClient, org_id: str, email: str, role: str = "user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "123456",
            "role": role,
            "organization_id": org_id,
            "organization_role": "member",
        },
    )
    return _login(client, email)


def test_admin_sem_ownership_bloqueado_ao_pedir_nivel_diferente_de_info():
    client, _ = _client()
    _, admin_token, _ = _setup_owner_and_non_owner_admin(client)

    response = client.get(
        "/api/v1/logs",
        params={"level": "WARN"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 403


def test_admin_sem_ownership_ve_apenas_info_por_padrao():
    client, _ = _client()
    owner_token, admin_token, _ = _setup_owner_and_non_owner_admin(client)
    # Generates a WARN-level "auth.login.failed" entry scoped to the shared org.
    client.post(
        "/api/v1/auth/login", json={"email": "owner@test.com", "password": "wrong"}
    )

    response = client.get("/api/v1/logs", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    logs = response.json()["data"]
    assert len(logs) >= 1
    assert all(entry["level"] == "INFO" for entry in logs)


def test_owner_ve_todos_os_niveis():
    client, _ = _client()
    owner_token, admin_token, _ = _setup_owner_and_non_owner_admin(client)
    client.post(
        "/api/v1/auth/login", json={"email": "owner@test.com", "password": "wrong"}
    )

    response = client.get(
        "/api/v1/logs",
        params={"level": "WARN"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    logs = response.json()["data"]
    assert any(entry["level"] == "WARN" for entry in logs)


def test_admin_dono_do_proprio_tenant_nao_e_restringido():
    """Ownership, not the "admin" role label, is what removes the restriction —
    an admin who auto-created (and therefore owns) their own org sees every
    level, same as any other owner.
    """
    client, _ = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "solo-admin@test.com", "password": "123456", "role": "admin"},
    )
    token = _login(client, "solo-admin@test.com")
    client.post(
        "/api/v1/auth/login", json={"email": "solo-admin@test.com", "password": "wrong"}
    )

    response = client.get(
        "/api/v1/logs", params={"level": "WARN"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert any(entry["level"] == "WARN" for entry in response.json()["data"])


def test_user_comum_nao_acessa_logs():
    client, _ = _client()
    _, _, org_id = _setup_owner_and_non_owner_admin(client)
    user_token = _register_member(client, org_id, "user@test.com")

    response = client.get("/api/v1/logs", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 403


def test_user_comum_nao_acessa_metrics():
    client, _ = _client()
    _, _, org_id = _setup_owner_and_non_owner_admin(client)
    user_token = _register_member(client, org_id, "user@test.com")

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 403


def test_user_comum_nao_acessa_audit():
    client, _ = _client()
    _, _, org_id = _setup_owner_and_non_owner_admin(client)
    user_token = _register_member(client, org_id, "user@test.com")

    response = client.get(
        "/api/v1/audit/events", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403


def test_admin_sem_ownership_acessa_metrics_sem_restricao_de_nivel():
    """Metrics are aggregated, non-PII — no INFO-only style restriction applies,
    unlike logs.
    """
    client, _ = _client()
    _, admin_token, _ = _setup_owner_and_non_owner_admin(client)

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200


def test_admin_sem_ownership_acessa_audit_sem_restricao():
    client, _ = _client()
    _, admin_token, _ = _setup_owner_and_non_owner_admin(client)

    response = client.get(
        "/api/v1/audit/events", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200


def test_admin_sem_ownership_com_nivel_info_explicito_funciona():
    client, _ = _client()
    _, admin_token, _ = _setup_owner_and_non_owner_admin(client)

    response = client.get(
        "/api/v1/logs",
        params={"level": "INFO"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
