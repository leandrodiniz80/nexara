import pytest
from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.core.config import settings
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer

TOKEN = "convite-de-teste-123"
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
CLOSED = "Cadastro disponível apenas por convite."


@pytest.fixture
def client(monkeypatch):
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    app.dependency_overrides[get_platform_container] = lambda: container
    test_client = TestClient(app)

    # Seed an admin while registration is still open, then lock it down.
    test_client.post(
        REGISTER, json={"email": "admin@nexara.com", "password": "senha-admin", "role": "admin"}
    )
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite")
    monkeypatch.setattr(settings, "REGISTRATION_INVITE_TOKEN", TOKEN)
    return test_client


def _admin_headers(client):
    token = client.post(LOGIN, json={"email": "admin@nexara.com", "password": "senha-admin"})
    return {"Authorization": f"Bearer {token.json()['data']['token']}"}


def _detail(response):
    body = response.json()
    return body.get("detail") or body["errors"][0]["message"]


def test_anonymous_register_is_closed(client):
    response = client.post(REGISTER, json={"email": "bot@spam.com", "password": "12345678"})
    assert response.status_code == 403
    assert _detail(response) == CLOSED
    assert (
        client.post(LOGIN, json={"email": "bot@spam.com", "password": "12345678"}).status_code
        == 401
    )


def test_wrong_invite_token_gets_the_same_generic_answer(client):
    response = client.post(
        REGISTER,
        json={"email": "bot@spam.com", "password": "12345678"},
        headers={"X-Invite-Token": "chute"},
    )
    assert response.status_code == 403
    assert _detail(response) == CLOSED


def test_closed_when_no_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_INVITE_TOKEN", "")
    response = client.post(
        REGISTER, json={"email": "a@b.com", "password": "12345678"}, headers={"X-Invite-Token": ""}
    )
    assert response.status_code == 403


def test_valid_invite_creates_account_in_its_own_organization(client):
    response = client.post(
        REGISTER,
        json={"email": "cliente@empresa.com", "password": "senha-forte"},
        headers={"X-Invite-Token": TOKEN},
    )
    assert response.status_code == 200
    login = client.post(LOGIN, json={"email": "cliente@empresa.com", "password": "senha-forte"})
    assert login.status_code == 200


@pytest.mark.parametrize(
    "extra",
    [
        {"organization_id": "org-de-outra-empresa"},
        {"organization_role": "owner"},
        {"role": "admin"},
        {"permissions": ["*"]},
    ],
)
def test_invite_cannot_set_privileged_fields(client, extra):
    response = client.post(
        REGISTER,
        json={"email": "intruso@x.com", "password": "senha-forte", **extra},
        headers={"X-Invite-Token": TOKEN},
    )
    assert response.status_code == 403
    assert _detail(response) == CLOSED
    assert (
        client.post(LOGIN, json={"email": "intruso@x.com", "password": "senha-forte"}).status_code
        == 401
    )


def test_password_minimum_length(client):
    response = client.post(
        REGISTER,
        json={"email": "c@empresa.com", "password": "1234567"},
        headers={"X-Invite-Token": TOKEN},
    )
    assert response.status_code == 422


def test_invalid_email_is_rejected(client):
    response = client.post(
        REGISTER,
        json={"email": "nao-e-email", "password": "senha-forte"},
        headers={"X-Invite-Token": TOKEN},
    )
    assert response.status_code == 422


def test_register_attempts_are_rate_limited_per_ip(client):
    statuses = [
        client.post(
            REGISTER, json={"email": f"bot{i}@spam.com", "password": "12345678"}
        ).status_code
        for i in range(6)
    ]
    assert statuses[:5] == [403] * 5
    assert statuses[5] == 429


def test_admin_can_still_create_accounts_with_any_field(client):
    response = client.post(
        REGISTER,
        json={
            "email": "membro@empresa.com",
            "password": "senha-forte",
            "organization_role": "member",
        },
        headers=_admin_headers(client),
    )
    assert response.status_code == 200


def test_login_is_unaffected_by_invite_mode(client):
    assert (
        client.post(
            LOGIN, json={"email": "admin@nexara.com", "password": "senha-admin"}
        ).status_code
        == 200
    )
    assert (
        client.post(LOGIN, json={"email": "admin@nexara.com", "password": "errada"}).status_code
        == 401
    )
