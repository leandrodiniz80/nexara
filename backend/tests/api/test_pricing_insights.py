"""Tests for GET /billing/pricing-insights (Sprint 282).

Same established local `_client()`/`_login()` helper pattern as the
other billing test files (test_billing_analytics.py onward).
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client(audit=None) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=audit)
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app), container


def _login(client: TestClient, email: str, role: str = "user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "role": role},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_sem_autenticacao_bloqueia():
    client, _ = _client()

    response = client.get("/api/v1/billing/pricing-insights")

    assert response.status_code == 401


def test_usuario_nao_admin_bloqueia():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/pricing-insights", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_admin_recebe_estrutura_correta():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/pricing-insights", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data["experiments"].keys()) == {"control", "price_up", "price_down"}
    for group in data["experiments"].values():
        assert "conversion_rate" in group
        assert "mrr" in group
    assert data["recommendation"]["recommended_strategy"] in ("increase", "decrease", "keep")
    assert "confidence" in data["recommendation"]
    assert "reason" in data["recommendation"]


def test_nao_altera_nenhum_plano_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    client.get(
        "/api/v1/billing/pricing-insights", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert container.auth().get_organization_plan(org_a) == "free"


def test_audita_o_acesso():
    audit = PlatformAudit(storage=None)
    client, container = _client(audit=audit)
    token = _login(client, "admin@test.com", role="admin")

    client.get(
        "/api/v1/billing/pricing-insights", headers={"Authorization": f"Bearer {token}"}
    )

    events = container.audit.get_events(event="pricing_insights_access")
    assert len(events) == 1
