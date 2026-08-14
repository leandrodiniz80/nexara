"""Tests for the Sprint 274 fields on GET /billing/analytics.

Same established local `_client()`/`_login()` helper pattern as
test_billing_analytics.py (Sprint 273) — the spec's own test used an
undeclared `client`/`admin_headers` pytest fixture pair, which don't
exist anywhere in this codebase's test suite.
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


def test_extended_metrics_present():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "mrr" in data
    assert "arr" in data
    assert "active_customers" in data
    assert "churn_rate" in data
    assert "ltv" in data


def test_sprint_273_fields_ainda_presentes():
    """Sprint 274's own rule: don't alter Sprint 273's existing logic —
    confirm the historical/cohort fields are still returned alongside
    the new current-state ones."""
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    data = response.json()["data"]
    assert "revenue_series" in data
    assert "growth_rate" in data
    assert "plan_distribution" in data
    assert "churn_series" in data


def test_mrr_reflete_apenas_organizacoes_pagantes():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    assert data["mrr"] == 99
    assert data["arr"] == 99 * 12
    assert data["active_customers"] == 1
