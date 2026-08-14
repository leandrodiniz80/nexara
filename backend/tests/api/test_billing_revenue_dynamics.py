"""Tests for the Sprint 275 fields on GET /billing/analytics.

Same established local `_client()`/`_login()` helper pattern as
test_billing_analytics.py (Sprint 273)/test_billing_analytics_extended.py
(Sprint 274) — the spec's own test used an undeclared `client`/
`admin_headers` pytest fixture pair, which don't exist anywhere in this
codebase's test suite.
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


def test_revenue_dynamics_fields_present():
    client, _ = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "revenue_by_plan" in data
    assert "expansion_revenue" in data
    assert "contraction_revenue" in data
    assert "net_revenue_change" in data


def test_expansion_revenue_reflete_upgrade_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    assert data["expansion_revenue"] == 99
    assert data["contraction_revenue"] == 0
    assert data["net_revenue_change"] == 99


def test_contraction_revenue_reflete_downgrade_real():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")

    container.auth().set_organization_plan(org_a, "enterprise")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    assert data["expansion_revenue"] == 299
    assert data["contraction_revenue"] == 299 - 99
    assert data["net_revenue_change"] == 299 - (299 - 99)


def test_revenue_by_plan_reflete_organizacoes_pagantes():
    client, container = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    _login(client, "owner-a@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    response = client.get(
        "/api/v1/billing/analytics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    data = response.json()["data"]
    assert data["revenue_by_plan"] == {"pro": 99}
