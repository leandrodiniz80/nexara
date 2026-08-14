"""Tests for POST/GET/DELETE /cdn/metrics/webhook/channel and the
per-channel alert-routing behavior they enable (Sprint 258).

Real issues in the spec, fixed here — see cdn.py/loader_metrics.py/
alert_channels.py/webhook_queue.py for the implementation-level
explanation:

1. The spec's own router code (`def create_channel(...)`, sync, calling
   `get_metrics_store()` directly inside the body instead of receiving it
   via `Depends()`) bypasses FastAPI's dependency-override mechanism —
   every test using `app.dependency_overrides[get_metrics_store]` (the
   established pattern in this entire test suite) would silently hit the
   real production singleton instead. Fixed: `async def` + a normal
   `store: LoaderMetricsStore = Depends(get_metrics_store)` parameter,
   like every other endpoint in this router.
2. `store._channel_manager.add_channel(...)` reached into a private
   attribute directly from the router — the same encapsulation break
   already fixed for incident history (Sprint 253), debounce (Sprint
   251), and the webhook queue (Sprint 256). Fixed via
   `store.add_alert_channel()`/`get_alert_channels()`/
   `remove_alert_channel()`.
3. A bare `payload: dict` request body instead of a validated
   `CreateChannelRequest` — an unvalidated `severities` field could be
   any type (e.g. a string), which `get_active_channels()`'s
   `severity in c.get("severities", [])` would then silently misapply as
   substring containment.
4. `self._send_webhook(alert, tenant_id, ...)` (spec's Step 4) assumed a
   `tenant_id` that plainly doesn't exist inside `detect_anomalies()` —
   would have raised `NameError` immediately. Fixed by resolving tenant
   ownership per-alert via `resolver.get_owner`, passed through as
   `detect_anomalies(domains, resolve_tenant=resolver.get_owner, ...)`.
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
from app.platform.metrics.alert_channels import AlertChannelManager
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

    def ltrim(self, key, start, end):
        values = self._lists.get(key, [])
        self._lists[key] = values[start:] if end == -1 else values[start : end + 1]

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value, nx=False, ex=None):
        self._strings[key] = value
        return True

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


def _storage_with_channels(with_worker: bool = False):
    fake_client = _FakeRedisClient()
    channel_manager = AlertChannelManager(fake_client)
    queue = WebhookQueue(fake_client)
    storage = AggregatedRedisMetricsStorage(
        fake_client,
        incident_manager=IncidentManager(fake_client),
        webhook_queue=queue,
        channel_manager=channel_manager,
    )
    return storage, channel_manager, queue, fake_client


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


_CHANNEL_BODY = {
    "type": "slack",
    "url": "https://hooks.slack.com/services/x",
    "severities": ["critical", "high"],
}


# --- POST /metrics/webhook/channel -----------------------------------------


def test_create_channel_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.post("/api/v1/cdn/metrics/webhook/channel", json=_CHANNEL_BODY)

    assert res.status_code == 401


def test_create_channel_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json=_CHANNEL_BODY,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_create_channel_admin_sem_channel_manager_retorna_503():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json=_CHANNEL_BODY,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 503


def test_create_channel_admin_cria_com_sucesso():
    storage, _, _, _ = _storage_with_channels()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json=_CHANNEL_BODY,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["id"]
    assert body["enabled"] is True
    assert body["type"] == "slack"
    assert body["severities"] == ["critical", "high"]


def test_create_channel_rejeita_type_invalido():
    storage, _, _, _ = _storage_with_channels()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json={"type": "not-a-real-type", "url": "https://x.example.com", "severities": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 422


# --- GET /metrics/webhook/channel -------------------------------------------


def test_list_channels_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/webhook/channel")

    assert res.status_code == 401


def test_list_channels_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/channel", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_list_channels_vazio_por_padrao():
    storage, _, _, _ = _storage_with_channels()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/channel", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"items": []}


def test_list_channels_retorna_canais_criados():
    storage, _, _, _ = _storage_with_channels()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json=_CHANNEL_BODY,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    res = client.get(
        "/api/v1/cdn/metrics/webhook/channel", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["url"] == _CHANNEL_BODY["url"]


def test_list_channels_isolado_por_tenant():
    storage, _, _, _ = _storage_with_channels()
    client, container, _, _ = _client(storage)
    admin_a_token = _register_admin(client, "admin-a@test.com")
    admin_b_token = _register_admin(client, "admin-b@test.com")
    client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json=_CHANNEL_BODY,
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )

    res_b = client.get(
        "/api/v1/cdn/metrics/webhook/channel", headers={"Authorization": f"Bearer {admin_b_token}"}
    )

    assert res_b.json() == {"items": []}


# --- DELETE /metrics/webhook/channel/{id} -----------------------------------


def test_delete_channel_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.delete("/api/v1/cdn/metrics/webhook/channel/some-id")

    assert res.status_code == 401


def test_delete_channel_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.delete(
        "/api/v1/cdn/metrics/webhook/channel/some-id",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_delete_channel_admin_remove_com_sucesso():
    storage, _, _, _ = _storage_with_channels()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    created = client.post(
        "/api/v1/cdn/metrics/webhook/channel",
        json=_CHANNEL_BODY,
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    res = client.delete(
        f"/api/v1/cdn/metrics/webhook/channel/{created['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"status": "deleted"}

    listed = client.get(
        "/api/v1/cdn/metrics/webhook/channel", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert listed.json() == {"items": []}


def test_delete_channel_inexistente_ainda_retorna_200():
    storage, _, _, _ = _storage_with_channels()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.delete(
        "/api/v1/cdn/metrics/webhook/channel/does-not-exist",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200


# --- Routing: alerts are delivered only to the matching channel ------------


def test_alerta_e_enfileirado_apenas_para_canal_com_severidade_correspondente():
    """The end-to-end proof this sprint exists for: a tenant with two
    channels (one subscribed to "critical", one only to "low") gets a
    critical alert routed to exactly the first, with that channel's own
    URL and Slack-formatted payload — not the shared single-webhook queue
    from Sprint 256, and not the other, unrelated channel."""
    storage, channel_manager, queue, fake_client = _storage_with_channels()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    channel_manager.add_channel(
        org_id,
        {"type": "slack", "url": "https://critical.example.com", "severities": ["critical"]},
    )
    channel_manager.add_channel(
        org_id, {"type": "generic", "url": "https://low.example.com", "severities": ["low"]}
    )

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    items = queue.dequeue_batch(10)
    assert len(items) == 1
    assert items[0]["url"] == "https://critical.example.com"
    assert items[0]["payload"]["text"].startswith("🚨 Alert: broken.com")


def test_sem_canais_configurados_alerta_usa_fila_unica_do_sprint_256():
    """Full backward compatibility: a tenant/storage with no channels
    configured at all falls back to the original Sprint 256 behavior —
    the raw alert enqueued once, no channel routing involved."""
    storage, _, queue, fake_client = _storage_with_channels()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("broken.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "broken.com", hours_ago, total=100, errors=0)
    for _ in range(100):
        store.add({"domain": "broken.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    items = queue.dequeue_batch(10)
    assert len(items) == 1
    assert "url" not in items[0]
    assert items[0]["payload"]["domain"] == "broken.com"
