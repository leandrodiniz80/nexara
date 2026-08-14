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


def _login(client: TestClient, email: str, role: str = "user") -> str:
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": "123456", "role": role}
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_audit_isolado_por_tenant():
    client, _ = _client()
    token_a = _login(client, "admin-a@test.com", role="admin")
    token_b = _login(client, "admin-b@test.com", role="admin")

    events_a = client.get(
        "/api/v1/audit/events", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]
    events_b = client.get(
        "/api/v1/audit/events", headers={"Authorization": f"Bearer {token_b}"}
    ).json()["data"]

    assert any(e["email"] == "admin-a@test.com" for e in events_a)
    assert all(e["email"] != "admin-b@test.com" for e in events_a)
    assert any(e["email"] == "admin-b@test.com" for e in events_b)
    assert all(e["email"] != "admin-a@test.com" for e in events_b)


def test_metrics_isoladas_por_tenant_com_usuarios_no_mesmo_tenant():
    client, container = _client()
    token_owner = _login(client, "owner@test.com", role="admin")
    me_response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token_owner}"}
    )
    org_id = me_response.json()["data"]["organization_id"]

    client.post(
        "/api/v1/auth/register",
        json={"email": "teammate@test.com", "password": "123456", "organization_id": org_id},
    )

    token_other = _login(client, "other-admin@test.com", role="admin")

    metrics_owner = client.get(
        "/api/v1/metrics", headers={"Authorization": f"Bearer {token_owner}"}
    ).json()["data"]["metrics"]
    metrics_other = client.get(
        "/api/v1/metrics", headers={"Authorization": f"Bearer {token_other}"}
    ).json()["data"]["metrics"]

    # owner's tenant: owner@test.com + teammate@test.com = 2 registrations
    assert metrics_owner["counters"]["auth.register"] == 2
    # other-admin's tenant: only themselves = 1 registration
    assert metrics_other["counters"]["auth.register"] == 1


def test_logs_isolados_por_tenant():
    client, _ = _client()
    token_a = _login(client, "admin-a@test.com", role="admin")
    token_b = _login(client, "admin-b@test.com", role="admin")

    logs_a = client.get(
        "/api/v1/logs", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]
    logs_b = client.get(
        "/api/v1/logs", headers={"Authorization": f"Bearer {token_b}"}
    ).json()["data"]

    assert any(entry["metadata"].get("email") == "admin-a@test.com" for entry in logs_a)
    assert all(entry["metadata"].get("email") != "admin-b@test.com" for entry in logs_a)
    assert any(entry["metadata"].get("email") == "admin-b@test.com" for entry in logs_b)
    assert all(entry["metadata"].get("email") != "admin-a@test.com" for entry in logs_b)


def test_duas_organizacoes_mesma_rota_cada_uma_ve_so_a_propria():
    client, _ = _client()
    token_a = _login(client, "a@test.com", role="admin")
    token_b = _login(client, "b@test.com", role="admin")

    for token, own_email, other_email in [
        (token_a, "a@test.com", "b@test.com"),
        (token_b, "b@test.com", "a@test.com"),
    ]:
        response = client.get(
            "/api/v1/audit/events", headers={"Authorization": f"Bearer {token}"}
        )
        events = response.json()["data"]
        assert any(e["email"] == own_email for e in events)
        assert all(e["email"] != other_email for e in events)


def test_admin_nao_ve_dados_globais_apenas_o_proprio_tenant():
    """Explicit confirmation of the sprint's stated design decision: even a
    platform "admin" role only ever sees their own organization's observability
    data through these endpoints — there is no global/cross-tenant view.
    """
    client, _ = _client()
    token_a = _login(client, "admin-a@test.com", role="admin")
    _login(client, "admin-b@test.com", role="admin")

    events = client.get(
        "/api/v1/audit/events", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]
    logs = client.get(
        "/api/v1/logs", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]
    metrics = client.get(
        "/api/v1/metrics", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["data"]["metrics"]

    assert all(e["email"] != "admin-b@test.com" for e in events)
    assert all(entry["metadata"].get("email") != "admin-b@test.com" for entry in logs)
    # Only admin-a's own registration was counted in their tenant's metrics.
    assert metrics["counters"]["auth.register"] == 1
