"""Tests for POST/GET/DELETE /tenants/api-keys and API-key auth on
/metrics/alerts, /metrics/live-status, /metrics/chart/{domain} (Sprint
266, hardened in Sprint 267).

Real issues in the Sprint 266 spec, fixed there — see api_key_manager.py/
api_keys.py/cdn.py for the implementation-level explanation:

1. `ApiKeyManager.revoke_key()` deleted unconditionally, no ownership
   check — any tenant could revoke any other tenant's key.
2. `get_api_key_tenant()` always raised 401 for a missing header, making
   it unusable as the *optional*, session-or-API-key dependency Part 5
   of the spec explicitly asks the protected endpoints to support.
   Fixed with `get_optional_api_key_tenant()` (`None` when no header,
   403 only when a header *was* sent but is invalid) plus
   `_resolve_scope_with_api_key()` in cdn.py.
3. `container.api_keys()` — `PlatformContainer` has no Redis access
   anywhere; `ApiKeyManager` is wired via its own dependency module
   instead (`get_api_key_manager()`), mirroring `get_metrics_store()`'s
   already-established lazy-singleton pattern.

Sprint 267 (hashing/masking/rate limiting) changed `list_keys()`'s
return shape from raw strings to masked dicts — see
test_api_key_security.py for that sprint's own dedicated coverage; only
the one assertion here that depended on the old shape was updated.
`get_api_rate_limiter` is now also overridden per test, for the same
isolation reason every other lazy singleton dependency in this test
suite already is (a shared, un-overridden `ApiRateLimiter` would leak
counters across tests, even though in practice each test's key is
random enough that it's never actually observed).
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.api_keys import get_api_key_manager, get_api_rate_limiter
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.tenant.api_key_manager import ApiKeyManager, mask_api_key
from app.platform.tenant.api_rate_limiter import ApiRateLimiter


class _FakeClient:
    def __init__(self):
        self._strings: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._hashes: dict[str, dict] = {}

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value):
        self._strings[key] = value

    def delete(self, key):
        self._strings.pop(key, None)
        self._hashes.pop(key, None)

    def sadd(self, key, value):
        self._sets.setdefault(key, set()).add(value)

    def srem(self, key, value):
        self._sets.get(key, set()).discard(value)

    def smembers(self, key):
        return set(self._sets.get(key, set()))

    def hset(self, key, mapping):
        self._hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key):
        return dict(self._hashes.get(key, {}))

    def incr(self, key):
        self._strings[key] = str(int(self._strings.get(key, 0)) + 1)
        return int(self._strings[key])

    def expire(self, key, ttl):
        return True


def _client() -> tuple[
    TestClient, PlatformContainer, DomainTenantResolver, ApiKeyManager, LoaderMetricsStore
]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    resolver = DomainTenantResolver()
    fake_client = _FakeClient()
    api_key_manager = ApiKeyManager(fake_client)
    rate_limiter = ApiRateLimiter(fake_client)
    store = LoaderMetricsStore()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    app.dependency_overrides[get_api_key_manager] = lambda: api_key_manager
    app.dependency_overrides[get_api_rate_limiter] = lambda: rate_limiter
    app.dependency_overrides[get_metrics_store] = lambda: store
    return TestClient(app), container, resolver, api_key_manager, store


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


# --- POST /tenants/api-keys ------------------------------------------------


def test_create_api_key_sem_autenticacao_bloqueia():
    client, _, _, _, _ = _client()

    res = client.post("/api/v1/tenants/api-keys")

    assert res.status_code == 401


def test_create_api_key_funciona_para_o_owner():
    client, container, _, api_key_manager, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    key = res.json()["api_key"]
    assert key.startswith("ak_")
    org_id = container.auth().get_user_organization("owner@test.com")
    assert api_key_manager.get_tenant(key) == org_id


# --- GET /tenants/api-keys --------------------------------------------------


def test_list_api_keys_sem_autenticacao_bloqueia():
    client, _, _, _, _ = _client()

    res = client.get("/api/v1/tenants/api-keys")

    assert res.status_code == 401


def test_list_api_keys_vazio_por_padrao():
    client, _, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json() == {"items": []}


def test_list_api_keys_retorna_keys_criadas():
    client, _, _, _, _ = _client()
    token = _login(client, "owner@test.com")
    created = client.post(
        "/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"}
    ).json()["api_key"]

    res = client.get("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"})

    # Sprint 267: list_keys() now returns masked entries, never the raw
    # value — see test_api_key_security.py for masking-specific coverage.
    assert res.json()["items"][0]["key"] == mask_api_key(created)


def test_list_api_keys_isolado_por_tenant():
    client, _, _, _, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")
    client.post("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token_a}"})

    res_b = client.get("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token_b}"})

    assert res_b.json() == {"items": []}


# --- DELETE /tenants/api-keys -----------------------------------------------


def test_revoke_api_key_sem_autenticacao_bloqueia():
    client, _, _, _, _ = _client()

    res = client.request(
        "DELETE", "/api/v1/tenants/api-keys", json={"key": "ak_whatever"}
    )

    assert res.status_code == 401


def test_revoke_api_key_funciona():
    client, _, _, api_key_manager, _ = _client()
    token = _login(client, "owner@test.com")
    key = client.post(
        "/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"}
    ).json()["api_key"]

    res = client.request(
        "DELETE",
        "/api/v1/tenants/api-keys",
        json={"key": key},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"status": "revoked"}
    assert api_key_manager.get_tenant(key) is None


def test_revoke_api_key_de_outro_tenant_retorna_404_nao_revoga():
    """The core security fix: a tenant must not be able to revoke another
    tenant's key just by knowing its value."""
    client, _, _, api_key_manager, _ = _client()
    token_a = _login(client, "owner-a@test.com")
    token_b = _login(client, "owner-b@test.com")
    key_a = client.post(
        "/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token_a}"}
    ).json()["api_key"]

    res = client.request(
        "DELETE",
        "/api/v1/tenants/api-keys",
        json={"key": key_a},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert res.status_code == 404
    assert api_key_manager.get_tenant(key_a) is not None


def test_revoke_api_key_inexistente_retorna_404():
    client, _, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.request(
        "DELETE",
        "/api/v1/tenants/api-keys",
        json={"key": "ak_does_not_exist"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 404


# --- API-key auth on protected /metrics/* endpoints -------------------------


def test_live_status_com_api_key_valida_funciona():
    client, container, resolver, api_key_manager, store = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)
    key = api_key_manager.generate_key(org_id)

    res = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key})

    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "tenant"
    assert body["items"] == {"a.com": "healthy"}


def test_live_status_com_api_key_invalida_retorna_403():
    client, _, _, _, _ = _client()

    res = client.get(
        "/api/v1/cdn/metrics/live-status", headers={"X-API-Key": "ak_not_a_real_key"}
    )

    assert res.status_code == 403


def test_live_status_sem_session_e_sem_api_key_retorna_401():
    client, _, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/live-status")

    assert res.status_code == 401


def test_live_status_continua_funcionando_apenas_com_sessao():
    """Backward compatibility (Part 5's own explicit requirement): a
    caller with no API key at all still authenticates via session, same
    as before this sprint."""
    client, container, resolver, _, _ = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/live-status", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json()["scope"] == "tenant"


def test_api_key_nunca_acessa_dominios_de_outro_tenant():
    client, container, resolver, api_key_manager, _ = _client()
    _login(client, "owner-a@test.com")
    _login(client, "owner-b@test.com")
    org_a = container.auth().get_user_organization("owner-a@test.com")
    org_b = container.auth().get_user_organization("owner-b@test.com")
    resolver.register_domain("a.com", org_a)
    resolver.register_domain("b.com", org_b)
    key_b = api_key_manager.generate_key(org_b)

    res = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key_b})

    assert res.json()["items"] == {"b.com": "healthy"}


def test_api_key_e_sempre_escopo_tenant_nunca_global():
    """Even if the underlying organization happens to have an admin user,
    an API key must never escalate to global/cross-tenant scope."""
    client, container, resolver, api_key_manager, _ = _client()
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@test.com", "password": "123456", "role": "admin"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "admin@test.com", "password": "123456"}
    ).json()
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("admin-owned.com", org_id)
    other_org = "some-other-org"
    resolver.register_domain("other.com", other_org)
    key = api_key_manager.generate_key(org_id)

    res = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key})

    body = res.json()
    assert body["scope"] == "tenant"
    assert "other.com" not in body["items"]


def test_chart_com_api_key_respeita_ownership():
    client, container, resolver, api_key_manager, store = _client()
    org_id = "tenant-a"
    resolver.register_domain("a.com", org_id)
    key = api_key_manager.generate_key(org_id)

    allowed = client.get("/api/v1/cdn/metrics/chart/a.com", headers={"X-API-Key": key})
    denied = client.get("/api/v1/cdn/metrics/chart/not-mine.com", headers={"X-API-Key": key})

    assert allowed.status_code == 200
    assert denied.status_code == 403


def test_alerts_endpoint_com_api_key_funciona():
    client, container, resolver, api_key_manager, store = _client()
    org_id = "tenant-a"
    resolver.register_domain("a.com", org_id)
    key = api_key_manager.generate_key(org_id)

    res = client.get("/api/v1/cdn/metrics/alerts", headers={"X-API-Key": key})

    assert res.status_code == 200
    assert res.json()["scope"] == "tenant"
