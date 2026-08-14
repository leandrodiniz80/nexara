from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client() -> TestClient:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    app.dependency_overrides[get_platform_container] = lambda: container
    return TestClient(app)


def _login(client: TestClient, email: str, role: str = "user", organization_id=None) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "123456",
            "role": role,
            "organization_id": organization_id,
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_audit_events_sem_token_bloqueia():
    client = _client()

    response = client.get("/api/v1/audit/events")

    assert response.status_code == 401


def test_audit_events_sem_role_adequada_bloqueia():
    client = _client()

    owner_token = _login(client, "owner@test.com", role="user")
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    org_id = me_response.json()["data"]["organization_id"]

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "member@test.com",
            "password": "123456",
            "role": "user",
            "organization_id": org_id,
            "organization_role": "member",
        },
    )
    login_response = client.post(
        "/api/v1/auth/login", json={"email": "member@test.com", "password": "123456"}
    )
    member_token = login_response.json()["data"]["token"]

    response = client.get(
        "/api/v1/audit/events", headers={"Authorization": f"Bearer {member_token}"}
    )

    assert response.status_code == 403


def test_audit_events_com_role_admin_funciona():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    events = response.json()["data"]
    assert isinstance(events, list)
    assert any(e["event"] == "user_registered" for e in events)


def test_audit_events_com_organization_role_owner_funciona():
    client = _client()
    # organization_id omitido -> auto-cria org e vira owner automaticamente
    token = _login(client, "owner@test.com", role="user")

    response = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_audit_events_nao_expoe_dados_sensiveis():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token}"})

    body_text = response.text
    assert "123456" not in body_text
    assert token not in body_text


def test_audit_events_filtro_por_event_via_query_param():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/audit/events",
        params={"event": "user_registered"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    events = response.json()["data"]
    assert len(events) >= 1
    assert all(e["event"] == "user_registered" for e in events)


def test_audit_events_filtro_por_email_via_query_param():
    client = _client()
    admin_token = _login(client, "admin@test.com", role="admin")
    me_response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"}
    )
    org_id = me_response.json()["data"]["organization_id"]

    # A teammate in the SAME org — filtering by email only makes sense within a
    # tenant the caller can already see; a different org would be invisible
    # regardless of this filter (see the cross-tenant test below).
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "teammate@test.com",
            "password": "123456",
            "organization_id": org_id,
        },
    )

    response = client.get(
        "/api/v1/audit/events",
        params={"email": "teammate@test.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    events = response.json()["data"]
    assert len(events) >= 1
    assert all(e["email"] == "teammate@test.com" for e in events)


def test_audit_events_e_automaticamente_escopado_ao_proprio_tenant():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")
    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_response.json()["data"]["organization_id"]

    response = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    events = response.json()["data"]
    assert len(events) >= 1
    assert all(e["organization_id"] == org_id for e in events)


def test_audit_events_ignora_tentativa_de_ver_outra_organizacao_via_query_param():
    """The `organization_id` query param no longer exists — a caller cannot ask to
    see another tenant's events by passing one. This is the actual security fix:
    previously any admin/owner could pass an arbitrary `organization_id` and see
    that org's audit trail.
    """
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    other_org_response = client.post(
        "/api/v1/auth/register",
        json={"email": "other-admin@test.com", "password": "123456", "role": "admin"},
    )
    assert other_org_response.status_code == 200
    other_login = client.post(
        "/api/v1/auth/login", json={"email": "other-admin@test.com", "password": "123456"}
    )
    other_token = other_login.json()["data"]["token"]
    other_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"}
    )
    other_org_id = other_me.json()["data"]["organization_id"]

    response = client.get(
        "/api/v1/audit/events",
        params={"organization_id": other_org_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    events = response.json()["data"]
    assert all(e["organization_id"] != other_org_id for e in events)


def test_audit_events_limit_via_query_param():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get(
        "/api/v1/audit/events",
        params={"limit": 1},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_audit_events_sem_query_params_usa_limit_padrao_100():
    client = _client()
    token = _login(client, "admin@test.com", role="admin")

    response = client.get("/api/v1/audit/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()["data"]) <= 100
