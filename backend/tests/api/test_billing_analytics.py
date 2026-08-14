"""Tests for GET /billing/analytics (Sprint 273).

Same established local `_client()`/`_login()` helper pattern as
test_billing_dashboard.py (Sprint 272) — the spec's own tests used
undeclared `client`/`admin_headers` pytest fixtures, which don't exist
anywhere in this codebase's test suite.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client() -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app), container


def _login(client: TestClient, email: str, role: str = "user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "role": role},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_analytics_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/analytics")

    assert response.status_code == 401


def test_analytics_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_analytics_admin_retorna_estrutura_esperada():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "revenue_series" in data
    assert "growth_rate" in data
    assert "plan_distribution" in data
    assert "churn_series" in data


def test_analytics_reflete_planos_das_organizacoes():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    assert data["plan_distribution"]["pro"] == 1
    assert sum(entry["revenue"] for entry in data["revenue_series"]) == 99


def test_analytics_audita_o_acesso():
    from app.platform.audit.platform_audit import PlatformAudit

    app = create_app()
    container = PlatformContainer(
        bootstrap=PlatformBootstrap(), audit=PlatformAudit(storage=None)
    )
    app.dependency_overrides[get_platform_container] = lambda: container
    client = TestClient(app)
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    events = [e["event"] for e in container.audit.get_events()]
    assert "billing_analytics_access" in events
