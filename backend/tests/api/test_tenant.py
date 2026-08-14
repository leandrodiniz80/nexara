from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_platform_container
from app.api.middleware.tenant import TenantMiddleware
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _probe_app(container: PlatformContainer) -> FastAPI:
    """A minimal, throwaway app — not `create_app()` — used only to observe
    `TenantMiddleware`'s effect on `request.state` without touching any
    production route (this sprint lays groundwork, it doesn't change the API).
    """
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.dependency_overrides[get_platform_container] = lambda: container

    @app.get("/probe")
    async def probe(request: Request) -> dict:
        return {"tenant_organization_id": getattr(request.state, "tenant_organization_id", None)}

    return app


def _client(container: PlatformContainer) -> TestClient:
    return TestClient(_probe_app(container))


def test_tenant_middleware_extrai_organization_id_do_token_valido():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    session = container.auth().login("user@test.com", "123456")
    org_id = container.auth().get_user_organization("user@test.com")

    response = _client(container).get(
        "/probe", headers={"Authorization": f"Bearer {session['token']}"}
    )

    assert response.status_code == 200
    assert response.json()["tenant_organization_id"] == org_id


def test_tenant_middleware_sem_token_nao_seta_nada():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    response = _client(container).get("/probe")

    assert response.status_code == 200
    assert response.json()["tenant_organization_id"] is None


def test_tenant_middleware_token_invalido_nao_quebra():
    container = PlatformContainer(bootstrap=PlatformBootstrap())

    response = _client(container).get(
        "/probe", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 200
    assert response.json()["tenant_organization_id"] is None


def test_tenant_middleware_header_sem_bearer_prefix_e_ignorado():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    session = container.auth().login("user@test.com", "123456")

    response = _client(container).get(
        "/probe", headers={"Authorization": session["token"]}
    )

    assert response.status_code == 200
    assert response.json()["tenant_organization_id"] is None


def test_tenant_middleware_isola_organizacoes_diferentes():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("a@test.com", "123456")
    container.auth().register_user("b@test.com", "123456")

    session_a = container.auth().login("a@test.com", "123456")
    session_b = container.auth().login("b@test.com", "123456")

    org_a = container.auth().get_user_organization("a@test.com")
    org_b = container.auth().get_user_organization("b@test.com")
    assert org_a != org_b

    client = _client(container)

    response_a = client.get("/probe", headers={"Authorization": f"Bearer {session_a['token']}"})
    response_b = client.get("/probe", headers={"Authorization": f"Bearer {session_b['token']}"})

    assert response_a.json()["tenant_organization_id"] == org_a
    assert response_b.json()["tenant_organization_id"] == org_b


def test_tenant_middleware_nao_usa_current_token_do_container():
    """The middleware must never call container.login()/set_tenant() on the
    shared container — those mutate single-actor-only state (`_current_token`
    and `_tenant_context`) that would corrupt it across concurrent requests.
    Confirm both stay exactly as they were (never set) after the middleware
    resolves a perfectly valid token for a perfectly real user.
    """
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("user@test.com", "123456")
    session = container.auth().login("user@test.com", "123456")

    assert container._current_token is None
    assert container._tenant_context is None

    response = _client(container).get(
        "/probe", headers={"Authorization": f"Bearer {session['token']}"}
    )

    assert response.json()["tenant_organization_id"] is not None
    assert container._current_token is None
    assert container._tenant_context is None


def test_bloqueio_cross_tenant_apos_middleware_resolver_tenant():
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    container.auth().register_user("owner@test.com", "123456")
    other_org = container.auth().create_organization("Other Org")
    session = container.auth().login("owner@test.com", "123456")

    response = _client(container).get(
        "/probe", headers={"Authorization": f"Bearer {session['token']}"}
    )
    resolved_tenant = response.json()["tenant_organization_id"]

    assert resolved_tenant != other_org
