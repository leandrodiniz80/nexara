"""Tests for the Sprint 277 fields on GET /billing/analytics.

Same established local `_client()`/`_login()` helper pattern as the
Sprint 273-276 billing test files. The 401/403 auth-guard checks are
already covered by test_billing_analytics.py (Sprint 273) and every
extension file since, so they aren't repeated here again — this file
focuses on what Sprint 277 actually adds.
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


def test_novos_campos_de_ia_presentes():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "churn_prediction" in data
    assert "upgrade_recommendations" in data
    assert "predicted_ltv" in data


def test_estrutura_valida():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    data = response.json()["data"]
    assert isinstance(data["churn_prediction"], list)
    assert isinstance(data["upgrade_recommendations"], list)
    assert isinstance(data["predicted_ltv"], float)


def test_campos_de_sprints_anteriores_ainda_presentes():
    """Sprint 277's own rule: only extend, never alter earlier sprints'
    logic -- confirm nothing already shipped got dropped."""
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    data = response.json()["data"]
    for field in ("forecast", "health_score", "anomalies", "mrr", "revenue_by_plan"):
        assert field in data


def test_churn_prediction_reflete_organizacao_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    org_ids = [c["org_id"] for c in data["churn_prediction"]]
    assert org_a in org_ids
