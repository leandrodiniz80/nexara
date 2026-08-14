"""Tests for GET /cdn/metrics/webhook/metrics (Sprint 257).

Real issues in the spec, fixed here — see cdn.py/webhook_queue.py for the
implementation-level explanation:

1. `success_rate = success / sent` is only meaningful if `sent` counts
   every delivery attempt, not just successful ones — the spec's own
   literal "on successful delivery -> increment success + sent" wording
   would make `sent` always equal `success`, so `success_rate` would
   always read 1.0 regardless of how much is actually failing. Fixed in
   `WebhookQueue.record_retry()`, which also bumps `sent`.
2. `role` is read fresh via `container.auth().get_user_role(...)`
   (through the existing `_require_admin()` helper, Sprint 256), not a
   stale value cached on the session dict — same pattern already used by
   every other admin-gated endpoint in this router.
3. Audit metadata doesn't duplicate `email`/`timestamp` — both are
   already recorded as top-level fields by `PlatformAudit.log_event()`
   itself; only `role` goes into the metadata dict, matching Sprint 255's
   own established shape.
"""

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.api.dependencies.tenant_resolver import DomainTenantResolver, get_domain_tenant_resolver
from app.platform.audit.platform_audit import PlatformAudit
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import AggregatedRedisMetricsStorage
from app.platform.metrics.webhook_queue import WebhookQueue


class _FakeRedisClient:
    def __init__(self):
        self._lists: dict[str, list[str]] = {}
        self._strings: dict[str, str] = {}

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

    def incr(self, key):
        self._strings[key] = str(int(self._strings.get(key, 0)) + 1)
        return int(self._strings[key])


def _storage_with_queue() -> tuple[AggregatedRedisMetricsStorage, WebhookQueue]:
    fake_client = _FakeRedisClient()
    queue = WebhookQueue(fake_client)
    storage = AggregatedRedisMetricsStorage(fake_client, webhook_queue=queue)
    return storage, queue


def _client(
    storage=None, with_audit: bool = True
) -> tuple[TestClient, PlatformContainer, LoaderMetricsStore, DomainTenantResolver]:
    app = create_app()
    container = PlatformContainer(
        bootstrap=PlatformBootstrap(), audit=PlatformAudit() if with_audit else None
    )
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


def test_webhook_metrics_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/webhook/metrics")

    assert res.status_code == 401


def test_webhook_metrics_usuario_comum_bloqueado_com_403():
    client, _, _, _ = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/metrics", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_webhook_metrics_admin_sem_queue_configurada_retorna_zeros():
    """No webhook configured at all -> zeros, not an error."""
    client, _, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/metrics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    assert res.json() == {
        "sent": 0,
        "success": 0,
        "failed": 0,
        "retry": 0,
        "success_rate": 0.0,
    }


def test_webhook_metrics_admin_ve_valores_reais():
    storage, queue = _storage_with_queue()
    queue.record_success()
    queue.record_success()
    queue.record_retry()
    client, _, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/metrics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["sent"] == 3
    assert body["success"] == 2
    assert body["retry"] == 1
    assert body["failed"] == 0
    assert body["success_rate"] == 2 / 3


def test_webhook_metrics_gera_evento_de_auditoria():
    client, container, _, _ = _client()
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/webhook/metrics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_webhook_metrics_access")
    assert len(events) == 1
    assert events[0]["email"] == "admin@test.com"
    assert events[0]["metadata"]["role"] == "admin"
    assert "timestamp" in events[0]


def test_webhook_metrics_acesso_por_usuario_comum_nao_gera_auditoria():
    """The 403 for a non-admin happens before any audit call — nothing to
    log for an access that never happened."""
    client, container, _, _ = _client()
    token = _login(client, "owner@test.com")

    client.get("/api/v1/cdn/metrics/webhook/metrics", headers={"Authorization": f"Bearer {token}"})

    assert container.audit.get_events(event="metrics_webhook_metrics_access") == []


def test_webhook_metrics_sem_platform_audit_configurado_nao_quebra():
    """container.audit defaults to None — must degrade gracefully, not
    500, matching every other optional-audit endpoint in this router."""
    client, _, _, _ = _client(with_audit=False)
    admin_token = _register_admin(client, "admin@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/webhook/metrics", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert res.status_code == 200
