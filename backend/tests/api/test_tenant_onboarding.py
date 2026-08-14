"""Tests for POST /tenants, POST /tenants/domains, GET /tenants/plan
(Sprint 265).

See tenants.py's own module docstring for the main architectural
decision this sprint required: "tenant" is `organization_id` throughout
this platform, and `PlatformAuth` already has a complete plan system —
this router is a thin, additive layer over both, not the spec's own
brand-new `Tenant`/`PlanManager` entities (which would have created a
second, independent source of truth for exactly the data Sprint 266's
Stripe billing integration will need to read/write next).

Real issues in the spec's own endpoint code, fixed here:

1. No ownership/role check at all on `create_tenant()`/`add_domain()` —
   any member of an organization, not just its owner, could rename it or
   burn through its domain quota. Added the same owner-only gate
   `PlatformContainer.upgrade_plan()` already applies to changing an
   organization's plan.
2. No duplicate/takeover check on `add_domain()` at all (the spec's own
   "BUGS A EVITAR" list explicitly calls this out as a requirement, but
   its own code sample doesn't implement it) — added via
   `resolver.get_owner()`, the same pre-write check its own docstring
   already anticipated ("used by the registration endpoint to detect
   domain takeover attempts before writing").
3. No normalization at all in the spec's own code sample (also called
   out in its own "BUGS A EVITAR") — added `strip().lower()`.
4. `len(domains) >= limits["domains"]` with no `-1` ("unlimited")
   handling — an Enterprise-plan tenant would hit a "domain limit
   reached" error on their very first domain if `limits["domains"]` were
   ever a real number instead of the `-1` sentinel this platform already
   uses for "no limit" elsewhere.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer


def _client() -> tuple[TestClient, PlatformContainer, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container, resolver


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def _add_member(client: TestClient, email: str, org_owner_token: str) -> str:
    """Registers `email` as a plain member of the *same* organization as
    whoever is logged in as `org_owner_token` — used to test that a
    non-owner member is correctly rejected by the owner-only gate."""
    org_id = client.get(
        "/api/v1/org/me", headers={"Authorization": f"Bearer {org_owner_token}"}
    ).json()["data"]["organization_id"]
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "123456", "organization_id": org_id},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


# --- POST /tenants -----------------------------------------------------


def test_create_tenant_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    res = client.post("/api/v1/tenants", json={"name": "Acme Inc"})

    assert res.status_code == 401


def test_create_tenant_funciona_para_o_owner():
    client, container, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/tenants", json={"name": "Acme Inc"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Acme Inc"
    assert body["tenant_id"]

    org_id = container.auth().get_user_organization("owner@test.com")
    assert container.auth().get_organization(org_id)["name"] == "Acme Inc"


# --- POST /tenants/domains -----------------------------------------------


def test_add_domain_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    res = client.post("/api/v1/tenants/domains", json={"domain": "acme.com"})

    assert res.status_code == 401


def test_add_domain_funciona():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "acme.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    org_id = container.auth().get_user_organization("owner@test.com")
    assert resolver.get_owner("acme.com") == org_id


def test_add_domain_normaliza_maiusculas_e_espacos():
    client, container, resolver = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "  ACME.com  "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["domain"] == "acme.com"
    org_id = container.auth().get_user_organization("owner@test.com")
    assert resolver.get_owner("acme.com") == org_id


def test_add_domain_ja_registrado_ao_proprio_tenant_retorna_409():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    client.post(
        "/api/v1/tenants/domains",
        json={"domain": "acme.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "acme.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 409


def test_add_domain_de_outro_tenant_e_bloqueado_prevencao_de_takeover():
    client, _, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")
    client.post(
        "/api/v1/tenants/domains",
        json={"domain": "taken.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "taken.com"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert res.status_code == 403


def test_add_domain_bloqueado_ao_atingir_limite_do_plano_free():
    """Free plan: domains=1 (Sprint 265's own new limit)."""
    client, _, _ = _client()
    token = _login(client, "owner@test.com")
    client.post(
        "/api/v1/tenants/domains",
        json={"domain": "first.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "second.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403
    assert "limit" in res.json()["detail"].lower()


def test_add_domain_plano_enterprise_nao_tem_limite():
    client, container, _ = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    container.auth().set_organization_plan(org_id, "enterprise")

    for i in range(10):
        res = client.post(
            "/api/v1/tenants/domains",
            json={"domain": f"domain{i}.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200


def test_add_domain_isolamento_entre_tenants():
    """Each tenant's own domain count/limit is independent -- tenant B
    adding domains never affects tenant A's own quota or vice versa."""
    client, container, resolver = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")

    res_a = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    res_b = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "b.com"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert res_a.status_code == 200
    assert res_b.status_code == 200
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    assert resolver.get_domains_for_organization(org_a) == ["a.com"]
    assert resolver.get_domains_for_organization(org_b) == ["b.com"]


def test_add_domain_membro_comum_bloqueado_apenas_owner_pode():
    client, _, _ = _client()
    owner_token = _login(client, "owner@test.com")
    member_token = _add_member(client, "member@test.com", owner_token)

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "acme.com"},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert res.status_code == 403


def test_add_domain_string_vazia_apos_normalizacao_retorna_422():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/tenants/domains",
        json={"domain": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422


# --- GET /tenants/plan ---------------------------------------------------


def test_get_plan_sem_autenticacao_bloqueia():
    client, _, _ = _client()

    res = client.get("/api/v1/tenants/plan")

    assert res.status_code == 401


def test_get_plan_padrao_e_free():
    client, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get("/api/v1/tenants/plan", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "free"
    assert body["limits"]["domains"] == 1
    assert body["limits"]["alerts_per_hour"] == 50


def test_get_plan_reflete_upgrade():
    client, container, _ = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    container.auth().set_organization_plan(org_id, "pro")

    res = client.get("/api/v1/tenants/plan", headers={"Authorization": f"Bearer {token}"})

    body = res.json()
    assert body["plan"] == "pro"
    assert body["limits"]["domains"] == 5
    assert body["limits"]["alerts_per_hour"] == 500


def test_get_plan_nao_exige_ser_owner():
    """Reading the plan is not owner-gated, unlike mutating actions."""
    client, _, _ = _client()
    owner_token = _login(client, "owner@test.com")
    member_token = _add_member(client, "member@test.com", owner_token)

    res = client.get("/api/v1/tenants/plan", headers={"Authorization": f"Bearer {member_token}"})

    assert res.status_code == 200
