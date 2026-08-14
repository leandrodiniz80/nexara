"""Tests for GET /billing/dashboard (Sprint 272).

The spec's own test used undeclared `client`/`auth_headers` pytest
fixtures — this codebase has no shared conftest fixtures for the test
client; every test file in this suite builds its own `_client()`/
`_login()` helpers (see test_billing.py, test_usage_endpoint.py, ...).
Replicated here instead, with an admin-capable `_login()` (mirrors
test_metrics.py's own helper) since the endpoint is admin-gated.
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


def test_dashboard_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/dashboard")

    assert response.status_code == 401


def test_dashboard_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_dashboard_admin_funciona():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert "mrr" in body
    assert "arr" in body
    assert "churn_rate" in body
    assert "arpu" in body
    assert "ltv" in body


def test_dashboard_reflete_planos_das_organizacoes():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    container.auth().set_organization_plan(org_a, "pro")
    container.auth().set_organization_plan(org_b, "enterprise")

    response = client.get(
        "/api/v1/billing/dashboard", headers={"Authorization": f"Bearer {admin_token}"}
    )

    body = response.json()["data"]
    assert body["mrr"] == 99 + 299
    assert body["active_customers"] == 2
    # admin's own org + org_a + org_b = 3 total organizations
    assert body["total_customers"] == 3


def test_dashboard_audita_o_acesso():
    from app.platform.audit.platform_audit import PlatformAudit

    app = create_app()
    container = PlatformContainer(
        bootstrap=PlatformBootstrap(), audit=PlatformAudit(storage=None)
    )
    app.dependency_overrides[get_platform_container] = lambda: container
    client = TestClient(app)
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/dashboard", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    events = [e["event"] for e in container.audit.get_events()]
    assert "billing_dashboard_access" in events
