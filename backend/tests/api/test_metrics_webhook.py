"""Tests for POST /cdn/metrics/webhook, GET /cdn/metrics/webhook/status,
and POST /cdn/metrics/webhook/process (Sprint 256: persisted, retried
webhook delivery — see webhook_queue.py/webhook_worker.py for the
implementation-level explanation of what changed from the spec).

Named test_metrics_webhook.py, not test_webhook.py (the spec's own
literal filename) — matching this router's established convention, where
every other /cdn/metrics/* endpoint already has its own test_metrics_*.py
file (test_metrics_alerts.py, test_metrics_audit.py, ...).

Real issues in the spec, fixed here — see cdn.py/webhook_queue.py/
webhook_worker.py for the implementation-level explanation:

1. `session.role` / `session["role"]` (whichever the spec used) instead of
   a fresh `container.auth().get_user_role(...)` lookup — the same class
   of bug already fixed for `/metrics/audit` (Sprint 255) and
   `_resolve_metrics_scope()` (Sprint 254): the session dict's own `role`
   is cached at login time, so an admin promoted after login (or a user
   who registered before any admin existed) would be checked against a
   stale value.
2. A bare `url: str` endpoint parameter (query string) instead of a
   proper Pydantic request body — every other POST endpoint in this
   codebase takes a JSON body.
3. `client.llen("webhook:queue")` reaching into a raw Redis client
   directly from the router — the same encapsulation break already fixed
   for incident history (Sprint 253) and debounce (Sprint 251); `client`
   was also never actually defined/injected in the spec's own snippet.
4. Nothing in the spec ever calls `WebhookWorker.process()` on an ongoing
   basis — `POST /metrics/webhook/process` (additive, not in the spec) is
   the fix; see cdn.py's docstring on that endpoint for the full
   reasoning.
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
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage
from app.platform.metrics.webhook_queue import WebhookQueue
from app.platform.metrics.webhook_worker import WebhookWorker


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


class _AlwaysSucceedsClient:
    def __init__(self, url, timeout_seconds=2.0):
        self.url = url

    def send(self, payload: dict) -> bool:
        return True


def _seed_bucket(client: _FakeRedisClient, domain: str, hours_ago: int, total: int, errors: int):
    bucket = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y%m%d%H")
    prefix = f"metrics:{domain}:bucket:{bucket}"
    client._strings[f"{prefix}:total"] = str(total)
    client._strings[f"{prefix}:success"] = str(total - errors)
    client._strings[f"{prefix}:error"] = str(errors)


def _storage_with_queue() -> tuple[AggregatedRedisMetricsStorage, WebhookQueue, _FakeRedisClient]:
    """`incident_manager` is included here (not just webhook_queue/
    webhook_worker): `LoaderMetricsStore._send_webhook()` is only ever
    called from `detect_anomalies()`'s incident-tracking branch — a
    storage with no `incident_manager` never reaches it at all, which
    would make `test_webhook_status_cresce_conforme_alertas_sao_enfileirados`
    below observe an always-empty queue regardless of this sprint's own
    code."""
    fake_client = _FakeRedisClient()
    queue = WebhookQueue(fake_client)
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)
    storage = AggregatedRedisMetricsStorage(
        fake_client,
        incident_manager=IncidentManager(fake_client),
        webhook_queue=queue,
        webhook_worker=worker,
    )
    return storage, queue, fake_client


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


# --- POST /metrics/webhook ------------------------------------------------


def test_set_webhook_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.post("/api/v1/cdn/metrics/webhook", json={"url": "https://hooks.example.com"})

    assert res.status_code == 401


def test_set_webhook_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook",
        json={"url": "https://hooks.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 403


def test_set_webhook_admin_sem_queue_configurada_retorna_503():
    """Default storage (InMemoryMetricsStorage) has no webhook_queue —
    graceful 503, not a 500/crash."""
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook",
        json={"url": "https://hooks.example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 503


def test_set_webhook_admin_com_queue_configurada_persiste_url():
    storage, queue, _ = _storage_with_queue()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook",
        json={"url": "https://hooks.example.com/webhook"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert queue.get_url() == "https://hooks.example.com/webhook"


# --- GET /metrics/webhook/status ------------------------------------------


def test_webhook_status_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/webhook/status")

    assert res.status_code == 401


def test_webhook_status_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/status", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_webhook_status_admin_sem_queue_configurada():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/status", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"configured": False, "queue_size": 0, "failed_count": 0}


def test_webhook_status_cresce_conforme_alertas_sao_enfileirados():
    """Queue grows on an alert when nothing has drained it yet (no URL
    configured) — proves detect_anomalies() -> _send_webhook() actually
    persists to the queue, not just an in-memory fire-and-forget."""
    storage, queue, fake_client = _storage_with_queue()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    resolver.register_domain("a.com", org_id)

    for hours_ago in range(1, 24):
        _seed_bucket(fake_client, "a.com", hours_ago, total=50, errors=0)
    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    client.get("/api/v1/cdn/metrics/alerts", headers={"Authorization": f"Bearer {admin_token}"})

    res = client.get(
        "/api/v1/cdn/metrics/webhook/status", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.json()["configured"] is True
    assert res.json()["queue_size"] == 1


# --- POST /metrics/webhook/process -----------------------------------------


def test_process_webhook_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.post("/api/v1/cdn/metrics/webhook/process")

    assert res.status_code == 401


def test_process_webhook_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/process", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_process_webhook_admin_sem_worker_configurado_retorna_503():
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/process", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 503


def test_process_webhook_admin_drena_fila_manualmente():
    storage, queue, _ = _storage_with_queue()
    queue.set_url("https://hooks.example.com/webhook")
    queue.enqueue({"domain": "a.com"})
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.post(
        "/api/v1/cdn/metrics/webhook/process", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"sent": 1, "failed": 0, "processed": 1}
    assert queue.queue_size() == 0
