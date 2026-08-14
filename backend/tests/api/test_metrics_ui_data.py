"""Tests for GET /cdn/metrics/chart/{domain}, GET /cdn/metrics/incidents/top,
and GET /cdn/metrics/live-status (Sprint 263).

Real issues in the spec, fixed here — see cdn.py/loader_metrics.py for
the implementation-level explanation:

1. `_resolve_metrics_scope(session, resolver, container)` — same wrong-
   argument-order-and-missing-`tenant_id` bug already fixed for
   `/metrics/alerts/insights` (Sprint 261) and `/metrics/dashboard/
   overview` (Sprint 262), reproduced in all 3 new endpoints here.
   `TypeError` on every call as written.
2. `get_time_series()` read `bucket.get("errors", 0)` (plural) —
   `summary_window()`/`_window_or_empty()` both key the error count
   `"error"` (singular). Every chart data point's `errors` field would
   silently always be `0`.
3. `get_top_incidents()`'s secondary sort key,
   `x.get("current", {}).get("error_rate", 0)`, is dead: active-incident
   records never carry a `"current"` key at all (only `severity` is ever
   persisted via `open_or_update()`), so it always fell back to `0` and
   never actually broke ties. Fixed using `started_at` instead.
4. No audit call for the `scope == "global"` case on any of the 3
   endpoints — every other `_resolve_metrics_scope()`-consuming endpoint
   since Sprint 255 audits a cross-tenant admin read.
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


class _FakeRedisClient:
    def __init__(self):
        self._strings: dict[str, str] = {}

    def incr(self, key):
        self._strings[key] = str(int(self._strings.get(key, 0)) + 1)
        return int(self._strings[key])

    def incrbyfloat(self, key, amount):
        self._strings[key] = str(float(self._strings.get(key, 0)) + amount)
        return float(self._strings[key])

    def get(self, key):
        return self._strings.get(key)

    def expire(self, key, ttl):
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


def _storage_with_incidents():
    fake_client = _FakeRedisClient()
    manager = IncidentManager(fake_client)
    storage = AggregatedRedisMetricsStorage(fake_client, incident_manager=manager)
    return storage, manager, fake_client


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


# --- GET /metrics/chart/{domain} -------------------------------------------


def test_chart_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/chart/a.com")

    assert res.status_code == 401


def test_chart_dominio_nao_pertencente_ao_tenant_retorna_403():
    client, container, _, resolver = _client()
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/chart/not-mine.com", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_chart_retorna_24_pontos_mais_recente_por_ultimo():
    storage, _, fake_client = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    _seed_bucket(fake_client, "a.com", hours_ago=0, total=50, errors=10)
    _seed_bucket(fake_client, "a.com", hours_ago=5, total=20, errors=0)

    res = client.get(
        "/api/v1/cdn/metrics/chart/a.com", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    body = res.json()
    assert body["domain"] == "a.com"
    assert len(body["items"]) == 24
    # Reversed: offset=23 (oldest) first, offset=0 (current hour) last.
    assert body["items"][-1]["hour_offset"] == 0
    assert body["items"][-1]["total"] == 50
    assert body["items"][-1]["errors"] == 10
    assert body["items"][0]["hour_offset"] == 23


def test_chart_admin_pode_consultar_qualquer_dominio():
    storage, _, fake_client = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    _seed_bucket(fake_client, "someone-elses.com", hours_ago=0, total=10, errors=1)

    res = client.get(
        "/api/v1/cdn/metrics/chart/someone-elses.com",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert res.status_code == 200
    assert res.json()["items"][-1]["total"] == 10


def test_chart_acesso_admin_gera_evento_de_auditoria():
    storage, _, _ = _storage_with_incidents()
    client, container, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/chart/a.com", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.chart"


def test_chart_storage_sem_summary_window_retorna_zeros_nao_vazio():
    """InMemoryMetricsStorage has no summary_window() — an honest
    24-entry, all-zero chart, matching domains_summary_window()'s own
    "zero, not empty/error" convention for the same situation."""
    client, container, store, resolver = _client()
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)

    res = client.get(
        "/api/v1/cdn/metrics/chart/a.com", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 24
    assert all(item["total"] == 0 for item in items)


# --- GET /metrics/incidents/top ---------------------------------------------


def test_top_incidents_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/incidents/top")

    assert res.status_code == 401


def test_top_incidents_ordenado_por_severidade():
    storage, manager, _ = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("medium.com", org_id)
    resolver.register_domain("critical.com", org_id)
    manager.open_or_update("medium.com", "error", {"severity": "medium"})
    manager.open_or_update("critical.com", "error", {"severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/incidents/top", headers={"Authorization": f"Bearer {token}"}
    )

    body = res.json()
    assert body["scope"] == "tenant"
    assert body["total"] == 2
    assert body["items"][0]["domain"] == "critical.com"
    assert body["items"][1]["domain"] == "medium.com"


def test_top_incidents_limita_a_10():
    storage, manager, _ = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")
    org_id = container.auth().get_user_organization("admin@test.com")
    for i in range(15):
        domain = f"d{i}.com"
        resolver.register_domain(domain, org_id)
        manager.open_or_update(domain, "error", {"severity": "high"})

    res = client.get(
        "/api/v1/cdn/metrics/incidents/top", headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert len(res.json()["items"]) == 10


def test_top_incidents_admin_gera_evento_de_auditoria():
    storage, _, _ = _storage_with_incidents()
    client, container, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/incidents/top", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.incidents.top"


# --- GET /metrics/live-status ------------------------------------------


def test_live_status_sem_autenticacao_bloqueia():
    client, _, _, _ = _client()

    res = client.get("/api/v1/cdn/metrics/live-status")

    assert res.status_code == 401


def test_live_status_classifica_por_severidade():
    storage, manager, _ = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("healthy.com", org_id)
    resolver.register_domain("degraded.com", org_id)
    resolver.register_domain("critical.com", org_id)
    manager.open_or_update("degraded.com", "error", {"severity": "high"})
    manager.open_or_update("critical.com", "error", {"severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/live-status", headers={"Authorization": f"Bearer {token}"}
    )

    body = res.json()
    assert body["scope"] == "tenant"
    assert body["items"] == {
        "healthy.com": "healthy",
        "degraded.com": "degraded",
        "critical.com": "critical",
    }


def test_live_status_critical_tem_prioridade_sobre_high():
    """A domain with both a high- and a critical-severity active incident
    must end up "critical", regardless of processing order."""
    storage, manager, _ = _storage_with_incidents()
    client, container, store, resolver = _client(storage)
    token = _login(client, "owner@test.com")
    org_id = container.auth().get_user_organization("owner@test.com")
    resolver.register_domain("a.com", org_id)
    manager.open_or_update("a.com", "latency", {"severity": "high"})
    manager.open_or_update("a.com", "error", {"severity": "critical"})

    res = client.get(
        "/api/v1/cdn/metrics/live-status", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.json()["items"]["a.com"] == "critical"


def test_live_status_admin_gera_evento_de_auditoria():
    storage, _, _ = _storage_with_incidents()
    client, container, _, _ = _client(storage)
    admin_token = _register_admin(client, "admin@test.com")

    client.get(
        "/api/v1/cdn/metrics/live-status", headers={"Authorization": f"Bearer {admin_token}"}
    )

    events = container.audit.get_events(event="metrics_global_access")
    assert len(events) == 1
    assert events[0]["metadata"]["resource"] == "metrics.live_status"
