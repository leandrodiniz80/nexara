"""Tests for the Sprint 276 fields on GET /billing/analytics.

Same established local `_client()`/`_login()` helper pattern as the
Sprint 273/274/275 billing test files — the spec's own test format for
this sprint didn't specify concrete fixtures, but every prior sprint's
attempts at implicit `client`/`admin_headers` fixtures don't exist
anywhere in this codebase's test suite, so this follows the same local
pattern proactively.
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


def test_endpoint_protegido_sem_autenticacao():
    client, _ = _client()

    response = client.get("/api/v1/billing/analytics")

    assert response.status_code == 401


def test_endpoint_protegido_exige_admin():
    client, _ = _client()
    token = _login(client, "owner@test.com", role="user")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_novos_campos_presentes():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "forecast" in data
    assert "health_score" in data
    assert "anomalies" in data


def test_health_score_estrutura_correta():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    health = response.json()["data"]["health_score"]
    assert "average_score" in health
    assert "distribution" in health
    assert set(health["distribution"].keys()) == {"healthy", "risk", "critical"}


def test_forecast_e_anomalies_sao_listas():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    data = response.json()["data"]
    assert isinstance(data["forecast"], list)
    assert isinstance(data["anomalies"], list)


def test_sprint_273_a_275_fields_ainda_presentes():
    """Sprint 276's own rule: don't alter earlier sprints' logic —
    confirm every previously-shipped field is still returned alongside
    the new ones."""
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    data = response.json()["data"]
    for field in (
        "revenue_series",
        "growth_rate",
        "plan_distribution",
        "churn_series",
        "mrr",
        "arr",
        "active_customers",
        "churn_rate",
        "ltv",
        "revenue_by_plan",
        "expansion_revenue",
        "contraction_revenue",
        "net_revenue_change",
    ):
        assert field in data


def test_forecast_reflete_organizacao_paga_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    assert len(data["forecast"]) == 3
    assert all("month" in f and "projected_mrr" in f for f in data["forecast"])
