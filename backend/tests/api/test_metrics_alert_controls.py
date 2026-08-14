"""Tests for POST /cdn/metrics/alerts/silence, /unsilence, and GET
/cdn/metrics/alerts/silenced (Sprint 259), plus the anti-spam gate they
enable inside _send_webhook().

Real issues in the spec, fixed here — see cdn.py/alert_controls.py for
the implementation-level explanation:

1. `_require_admin(container, session)` — arguments swapped versus the
   real, established signature (`_require_admin(session, container)`,
   Sprint 256). As written, every one of these 3 endpoints would 500 on
   the very first call (`container.auth()` invoked on the actual
   `session` dict, which has no `.auth` attribute).
2. `payload["domain"]`/`payload.get("seconds", 3600)` on a bare
   `payload: dict` — a missing `domain` raises an uncaught `KeyError`
   (500) instead of a clean 422. Fixed with `SilenceAlertRequest`/
   `UnsilenceAlertRequest` bodies.
3. `store._storage._client.delete(key)` / `store._storage._client.keys(...)`
   — two levels of private-attribute reach-through from the router, and
   `KEYS` (not `SCAN`) for the listing endpoint, the same anti-pattern
   already fixed for `top_domains()` (Sprint 247). Fixed via
   `store.unsilence_alert()`/`store.list_silenced_alerts()`, with
   `AlertControlManager.list_silenced()` using `scan_iter`.
4. The spec's own `{"status": "not_supported"}` (a 200) for a missing
   `alert_controls` capability is inconsistent with every other write
   endpoint in this router's own established "optional capability -> 503"
   convention (`/metrics/webhook`, `/metrics/webhook/channel`) — the read
   endpoint (`GET .../silenced`) still degrades to 200/`{"items": []}`,
   matching `GET /metrics/webhook/channel`'s own convention.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.alert_controls import AlertControlManager
from app.platform.metrics.alert_digest import AlertDigestManager
from app.platform.metrics.alert_rate_limiter import AlertRateLimiter
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage
from app.platform.metrics.webhook_queue import WebhookQueue


class _FakeRedisClient:
    def __init__(self):
        self._lists: dict[str, list[str]] = {}
        self._strings: dict[str, str] = {}

    def incr(self, key):
        self._strings[key] = str(int(self._strings.get(key, 0)) + 1)
        return int(self._strings[key])

    def incrbyfloat(self, key, amount):
        self._strings[key] = str(float(self._strings.get(key, 0)) + amount)
        return float(self._strings[key])

    def expire(self, key, ttl):
        return True

    def rpush(self, key, value):
        self._lists.setdefault(key, []).append(value)

    def lpop(self, key):
        values = self._lists.get(key, [])
        if not values:
            return None
        return values.pop(0)

    def llen(self, key):
        return len(self._lists.get(key, []))

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def ltrim(self, key, start, end):
        values = self._lists.get(key, [])
        self._lists[key] = values[start:] if end == -1 else values[start : end + 1]

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._strings:
            return None

        self._strings[key] = str(value)
        return True

    def delete(self, key):
        self._strings.pop(key, None)

    def scan_iter(self, match=None):
        prefix = match.rstrip("*") if match else ""
        return [k for k in self._strings if k.startswith(prefix)]

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, client):
        self._client = client
        self._queued: list[tuple[str, tuple]] = []

    def __getattr__(self, name):
        def queue(*args):
            self._queued.append((name, args))
            return self

        return queue

    def execute(self):
        results = [getattr(self._client, name)(*args) for name, args in self._queued]
        self._queued = []
        return results


def _seed_bucket(client: _FakeRedisClient, domain: str, hours_ago: int, total: int, errors: int):
    bucket = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y%m%d%H")
    prefix = f"metrics:{domain}:bucket:{bucket}"
    client._strings[f"{prefix}:total"] = str(total)
    client._strings[f"{prefix}:success"] = str(total - errors)
    client._strings[f"{prefix}:error"] = str(errors)


def _storage_with_controls(with_webhook_queue: bool = True):
    fake_client = _FakeRedisClient()
    controls = AlertControlManager(fake_client)
    queue = WebhookQueue(fake_client) if with_webhook_queue else None
    storage = AggregatedRedisMetricsStorage(
        fake_client,
        incident_manager=IncidentManager(fake_client),
        webhook_queue=queue,
        alert_controls=controls,
    )
    return storage, controls, queue, fake_client


def _storage_with_digest():
    fake_client = _FakeRedisClient()
    controls = AlertControlManager(fake_client)
    digest = AlertDigestManager(fake_client)
    rate_limiter = AlertRateLimiter(fake_client)
    queue = WebhookQueue(fake_client)
    storage = AggregatedRedisMetricsStorage(
        fake_client,
        incident_manager=IncidentManager(fake_client),
        webhook_queue=queue,
        alert_controls=controls,
        alert_digest=digest,
        rate_limiter=rate_limiter,
    )
    return storage, controls, digest, rate_limiter, queue, fake_client


def _client(
    storage=None,
) -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap(), audit=PlatformAudit())
    store = LoaderMetricsStore(storage=storage)
    resolver = DomainTenantResolver()
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    app.dependency_overrides[get_domain_tenant_resolver] = lambda: resolver
    return TestClient(app), container, store, resolver


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def _register_admin(client: TestClient, email: str) -> str:
    client.post(
        "/api/v1/auth/register", json={"email": email, "password": "123456", "role": "admin"}
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


# --- POST /metrics/alerts/silence ------------------------------------------


def test_silence_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.post("/api/v1/cdn/metrics/alerts/silence", json={"domain": "a.com"})

    assert res.status_code == 401


def test_silence_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/silence",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_silence_sem_domain_no_corpo_retorna_422():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/silence",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 422


def test_silence_admin_sem_alert_controls_retorna_503():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/silence",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 503


def test_silence_admin_com_alert_controls_funciona():
    storage, controls, _, _ = _storage_with_controls()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/silence",
        json={"domain": "a.com", "seconds": 60},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"status": "silenced"}
    assert controls.is_silenced("a.com") is True


def test_silence_usa_default_de_3600_segundos():
    storage, controls, _, _ = _storage_with_controls()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    client.post(
        "/api/v1/cdn/metrics/alerts/silence",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert controls.is_silenced("a.com") is True


# --- POST /metrics/alerts/unsilence -----------------------------------------


def test_unsilence_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.post("/api/v1/cdn/metrics/alerts/unsilence", json={"domain": "a.com"})

    assert res.status_code == 401


def test_unsilence_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/unsilence",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_unsilence_admin_remove_o_silenciamento():
    storage, controls, _, _ = _storage_with_controls()
    controls.silence("a.com", 3600)
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/unsilence",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"status": "unsilenced"}
    assert controls.is_silenced("a.com") is False


def test_unsilence_admin_sem_alert_controls_retorna_503():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/unsilence",
        json={"domain": "a.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 503


# --- GET /metrics/alerts/silenced -------------------------------------------


def test_list_silenced_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/alerts/silenced")

    assert res.status_code == 401


def test_list_silenced_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/silenced", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_list_silenced_admin_sem_alert_controls_retorna_vazio_nao_503():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/silenced", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"items": []}


def test_list_silenced_admin_ve_dominios_silenciados():
    storage, controls, _, _ = _storage_with_controls()
    controls.silence("a.com", 3600)
    controls.silence("b.com", 3600)
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/silenced", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert sorted(res.json()["items"]) == ["a.com", "b.com"]


# --- Anti-spam gate wired into _send_webhook() ------------------------------


def test_dominio_silenciado_nao_recebe_webhook():
    storage, controls, queue, fake_client = _storage_with_controls()
    controls.silence("broken.com", 3600)
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    assert queue.queue_size() == 0


def test_dominio_nao_silenciado_recebe_webhook_normalmente():
    storage, _, queue, fake_client = _storage_with_controls()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    assert queue.queue_size() == 1


def test_cooldown_bloqueia_envio_repetido_de_webhook():
    """Two separate alert-opening cycles (resolve, then re-open) for the
    same domain+type within the 300s cooldown window must still only
    enqueue one webhook delivery -- proving the cooldown gate, not just
    incident-manager's own open/ongoing debounce (which already covers
    the "still open" case; this covers "closed and reopened quickly")."""
    storage, _, queue, fake_client = _storage_with_controls()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})
    assert queue.queue_size() == 1
    queue.dequeue_batch(10)  # drain, simulating the first delivery completing

    # Resolve the incident, then trigger a fresh "open" transition for the
    # same domain+type right away -- incident_manager alone would allow a
    # brand-new webhook here (it's a new "open", not "ongoing"); the
    # cooldown gate is what still blocks it.
    storage.incident_manager.resolve("broken.com", "error")
    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    assert queue.queue_size() == 0


# --- Sprint 260: rate limiting + digest --------------------------------


def test_dominio_com_rate_limit_excedido_vai_para_digest_nao_para_a_fila():
    storage, _, digest, rate_limiter, queue, fake_client = _storage_with_digest()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    # Pre-exhaust the rate limiter (default limit=5) directly, the same
    # way test_cooldown_bloqueia_envio_repetido_de_webhook pre-manipulates
    # incident_manager -- simpler and more deterministic than trying to
    # naturally trigger 6 distinct alert-open events through detection.
    for _ in range(5):
        rate_limiter.allow("broken.com")

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    assert queue.queue_size() == 0
    assert digest.size(org_id) == 1


def test_dominio_dentro_do_rate_limit_nao_vai_para_digest():
    storage, _, digest, _, queue, fake_client = _storage_with_digest()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    assert queue.queue_size() == 1
    assert digest.size(org_id) == 0


def test_dominio_silenciado_e_rate_limitado_nao_vai_para_digest():
    """Silence takes priority over rate-limit-driven digesting: an
    explicitly silenced domain must not leak into a digest an admin will
    later see, just because it also happens to be noisy."""
    storage, controls, digest, rate_limiter, queue, fake_client = _storage_with_digest()
    controls.silence("broken.com", 3600)
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})
    for _ in range(5):
        rate_limiter.allow("broken.com")

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    assert queue.queue_size() == 0
    assert digest.size(org_id) == 0


# --- POST /metrics/alerts/digest/flush --------------------------------


def test_flush_digest_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.post("/api/v1/cdn/metrics/alerts/digest/flush")

    assert res.status_code == 401


def test_flush_digest_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/digest/flush", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_flush_digest_admin_sem_alert_digest_retorna_vazio():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/digest/flush",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}


def test_flush_digest_admin_sem_alertas_acumulados_retorna_vazio():
    storage, *_ = _storage_with_digest()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/alerts/digest/flush",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}


def test_flush_digest_admin_retorna_alertas_agrupados():
    storage, _, digest, rate_limiter, queue, fake_client = _storage_with_digest()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})
    for _ in range(5):
        rate_limiter.allow("broken.com")

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})
    assert digest.size(org_id) == 1

    res = client.post(
        "/api/v1/cdn/metrics/alerts/digest/flush",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "digest"
    assert body["items"][0]["count"] == 1
    assert body["items"][0]["domains"] == ["broken.com"]
    assert digest.size(org_id) == 0


# --- GET /metrics/alerts/digest (Sprint 261, read-only) ---------------


def test_get_digest_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/alerts/digest")

    assert res.status_code == 401


def test_get_digest_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/digest", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_get_digest_admin_sem_alert_digest_retorna_vazio():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/digest", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}


def test_get_digest_admin_sem_alertas_pendentes_retorna_vazio():
    storage, *_ = _storage_with_digest()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/alerts/digest", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}


def test_get_digest_admin_ve_quantidade_pendente_sem_esvaziar():
    storage, _, digest, rate_limiter, queue, fake_client = _storage_with_digest()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})
    for _ in range(5):
        rate_limiter.allow("broken.com")

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    res = client.get(
        "/api/v1/cdn/metrics/alerts/digest", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"items": [{"pending": 1}], "total": 1}
    # Read-only: the digest must still be flushable afterward, unaffected
    # by having been peeked at.
    assert digest.size(org_id) == 1
