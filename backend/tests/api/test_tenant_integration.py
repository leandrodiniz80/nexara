from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.tenant import get_request_tenant_id
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client() -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app), container


def _login(client: TestClient, email: str, organization_id: str | None = None) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "organization_id": organization_id},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_org_me_isola_entre_duas_organizacoes():
    client, container = _client()

    token_a = _login(client, "a@test.com")
    token_b = _login(client, "b@test.com")

    response_a = client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token_a}"})
    response_b = client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token_b}"})

    org_a = response_a.json()["data"]["organization_id"]
    org_b = response_b.json()["data"]["organization_id"]

    assert org_a != org_b
    assert response_a.json()["data"]["user_count"] == 1
    assert response_b.json()["data"]["user_count"] == 1


def test_billing_plan_isola_entre_duas_organizacoes():
    client, container = _client()

    token_a = _login(client, "a@test.com")
    token_b = _login(client, "b@test.com")

    org_a = container.auth().get_user_organization("a@test.com")
    org_b = container.auth().get_user_organization("b@test.com")
    container.auth().set_organization_plan(org_a, "pro")

    plan_a = client.get("/api/v1/billing/plan", headers={"Authorization": f"Bearer {token_a}"})
    plan_b = client.get("/api/v1/billing/plan", headers={"Authorization": f"Bearer {token_b}"})

    assert plan_a.json()["data"]["plan"] == "pro"
    assert plan_b.json()["data"]["plan"] == "free"


def test_upgrade_de_uma_org_nao_afeta_a_outra():
    client, container = _client()

    owner_token = _login(client, "owner@test.com")
    other_owner_token = _login(client, "other-owner@test.com")

    client.post(
        "/api/v1/billing/upgrade",
        json={"plan": "enterprise"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    own_plan = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {owner_token}"}
    )
    other_plan = client.get(
        "/api/v1/billing/plan", headers={"Authorization": f"Bearer {other_owner_token}"}
    )

    assert own_plan.json()["data"]["plan"] == "enterprise"
    assert other_plan.json()["data"]["plan"] == "free"


def test_secure_demo_test_auth_retorna_tenant_id_correto_por_usuario():
    client, container = _client()

    token_a = _login(client, "a@test.com")
    token_b = _login(client, "b@test.com")
    org_a = container.auth().get_user_organization("a@test.com")
    org_b = container.auth().get_user_organization("b@test.com")

    response_a = client.get(
        "/api/v1/secure/test-auth", headers={"Authorization": f"Bearer {token_a}"}
    )
    response_b = client.get(
        "/api/v1/secure/test-auth", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response_a.json()["data"]["tenant_id"] == org_a
    assert response_b.json()["data"]["tenant_id"] == org_b
    assert org_a != org_b


def test_bloqueio_cross_tenant_quando_dependency_diverge_da_sessao():
    """`ensure_tenant_access` is the second half of the "validação dupla": even if
    something resolved a tenant_id that doesn't match the caller's own session
    (a bug, or a forged/mismatched value), the route must reject the request
    rather than serve another organization's data.
    """
    client, container = _client()
    token = _login(client, "user@test.com")
    other_org = container.auth().create_organization("Other Org")

    client.app.dependency_overrides[get_request_tenant_id] = lambda: other_org

    response = client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_bloqueio_cross_tenant_no_billing_tambem():
    client, container = _client()
    token = _login(client, "owner@test.com")
    other_org = container.auth().create_organization("Other Org")

    client.app.dependency_overrides[get_request_tenant_id] = lambda: other_org

    response = client.get("/api/v1/billing/plan", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_tenant_id_ausente_retorna_404_em_organizations():
    client, container = _client()
    token = _login(client, "user@test.com")

    client.app.dependency_overrides[get_request_tenant_id] = lambda: None

    response = client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


def test_isolamento_nao_depende_de_container_set_tenant():
    """No route in this sprint calls `container.set_tenant()` — isolation comes
    entirely from per-request `request.state`/dependency resolution. Confirm the
    container's single-actor tenant state was never touched by any of these calls.
    """
    client, container = _client()
    token_a = _login(client, "a@test.com")
    token_b = _login(client, "b@test.com")

    client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token_a}"})
    client.get("/api/v1/org/me", headers={"Authorization": f"Bearer {token_b}"})
    client.get("/api/v1/billing/plan", headers={"Authorization": f"Bearer {token_a}"})

    assert container._tenant_context is None
    assert container._current_token is None
