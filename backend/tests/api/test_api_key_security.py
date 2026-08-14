"""Dedicated endpoint-level security-hardening tests for API keys
(Sprint 267): creation still returns the full raw key, listing never
does, revocation actually removes the key, and API-key-authenticated
requests get rate-limited. See test_api_keys.py for the general CRUD/
auth coverage carried over from Sprint 266.
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
from app.platform.tenant.api_key_manager import ApiKeyManager, hash_api_key, mask_api_key
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
    TestClient, PlatformContainer, DomainTenantResolver, ApiKeyManager, ApiRateLimiter
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
    return TestClient(app), container, resolver, api_key_manager, rate_limiter


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


# --- create returns the full key, list never does ---------------------


def test_create_retorna_chave_completa_nao_mascarada():
    client, _, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"})

    key = res.json()["api_key"]
    assert key.startswith("ak_")
    assert "..." not in key
    assert len(key) > len(mask_api_key(key))


def test_list_nunca_expoe_a_chave_completa():
    client, _, _, _, _ = _client()
    token = _login(client, "owner@test.com")
    key = client.post(
        "/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"}
    ).json()["api_key"]

    res = client.get("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"})

    body = res.json()["items"][0]
    assert body["key"] == mask_api_key(key)
    assert key not in body["key"]
    assert "created_at" in body


def test_create_gera_evento_de_auditoria_com_valor_mascarado():
    client, container, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post("/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"})
    key = res.json()["api_key"]

    events = container.audit.get_events(event="api_key_created")
    assert len(events) == 1
    assert events[0]["metadata"]["masked_key"] == mask_api_key(key)
    assert key not in str(events[0])


# --- revoke actually removes the key ------------------------------------


def test_revoke_remove_a_chave_corretamente():
    client, container, resolver, api_key_manager, _ = _client()
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
    assert api_key_manager.get_tenant(key) is None
    # The key must no longer authenticate anything after revocation.
    denied = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key})
    assert denied.status_code == 403


def test_revoke_gera_evento_de_auditoria_com_valor_mascarado():
    client, container, _, _, _ = _client()
    token = _login(client, "owner@test.com")
    key = client.post(
        "/api/v1/tenants/api-keys", headers={"Authorization": f"Bearer {token}"}
    ).json()["api_key"]

    client.request(
        "DELETE",
        "/api/v1/tenants/api-keys",
        json={"key": key},
        headers={"Authorization": f"Bearer {token}"},
    )

    events = container.audit.get_events(event="api_key_revoked")
    assert len(events) == 1
    assert events[0]["metadata"]["masked_key"] == mask_api_key(key)


# --- rate limiting ----------------------------------------------------


def test_rate_limit_permite_ate_o_limite():
    client, container, resolver, api_key_manager, rate_limiter = _client()
    org_id = "tenant-a"
    resolver.register_domain("a.com", org_id)
    key = api_key_manager.generate_key(org_id)

    for _ in range(100):
        res = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key})
        assert res.status_code == 200


def test_rate_limit_retorna_429_apos_o_limite():
    client, container, resolver, api_key_manager, rate_limiter = _client()
    org_id = "tenant-a"
    resolver.register_domain("a.com", org_id)
    key = api_key_manager.generate_key(org_id)

    # Pre-exhaust the rate limiter directly (default limit=100), the same
    # way earlier sprints (e.g. Sprint 260) pre-arm a rate limiter rather
    # than making 100 real HTTP calls just to reach the threshold.
    key_hash = hash_api_key(key)
    for _ in range(100):
        rate_limiter.allow(key_hash)

    res = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key})

    assert res.status_code == 429


def test_rate_limit_e_isolado_por_key():
    client, container, resolver, api_key_manager, rate_limiter = _client()
    resolver.register_domain("a.com", "tenant-a")
    resolver.register_domain("b.com", "tenant-b")
    key_a = api_key_manager.generate_key("tenant-a")
    key_b = api_key_manager.generate_key("tenant-b")

    for _ in range(100):
        rate_limiter.allow(hash_api_key(key_a))

    exhausted = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key_a})
    still_ok = client.get("/api/v1/cdn/metrics/live-status", headers={"X-API-Key": key_b})

    assert exhausted.status_code == 429
    assert still_ok.status_code == 200


def test_rate_limit_nao_afeta_autenticacao_por_sessao():
    """Rate limiting is API-key-specific — a session-authenticated caller
    must be unaffected even if some API key is currently exhausted."""
    client, container, resolver, api_key_manager, rate_limiter = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)
    key = api_key_manager.generate_key(org_id)
    key_hash = hash_api_key(key)
    for _ in range(100):
        rate_limiter.allow(key_hash)

    res = client.get(
        "/api/v1/cdn/metrics/live-status", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
