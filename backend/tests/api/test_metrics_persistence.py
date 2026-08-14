"""Tests for the Sprint 244 storage-abstraction layer behind LoaderMetricsStore.

Important: despite this sprint's own framing ("Persistência real" / "reiniciou
-> perdeu tudo, resolvido"), `get_metrics_store()` still defaults to
`InMemoryMetricsStorage` — restarting the process still loses every event.
What this sprint actually delivers is a swappable storage *interface*
(matching `BrandingStorage`'s established pattern) plus a Redis-ready
adapter that isn't wired into production yet (see test_metrics_storage.py
for that adapter's own tests). These tests verify the injection seam works
end-to-end through the real API — not that data survives a restart, which
nothing in this sprint makes true.

The spec's own proposed "test_persistencia_simulada" created two independent
`TestClient`s from two `create_app()` calls and treated seeing the same data
in both as proof of "persistence" — but that only shows a Python
module-level global survives across two app instances *in the same
process*, which was already true before this sprint (it's just how a
lazy-singleton dependency behaves) and says nothing about surviving an
actual process restart. That test is intentionally not reproduced here.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.api_factory import create_app
from app.api.dependencies.auth import get_platform_container
from app.api.dependencies.metrics import get_metrics_store
from app.platform.bootstrap.platform_bootstrap import PlatformBootstrap
from app.platform.bootstrap.platform_container import PlatformContainer
from app.platform.metrics.alert_controls import AlertControlManager
from app.platform.metrics.alert_rate_limiter import AlertRateLimiter
from app.platform.metrics.incident_manager import IncidentManager
from app.platform.metrics.loader_metrics import LoaderMetricsStore
from app.platform.metrics.metrics_storage import (
    AggregatedRedisMetricsStorage,
    InMemoryMetricsStorage,
    MetricsStorage,
)
from app.platform.metrics.webhook_queue import WebhookQueue
from app.platform.metrics.webhook_worker import WebhookWorker
from app.platform.usage.usage_tracker import UsageTracker


class _RecordingStorage(MetricsStorage):
    """A minimal fake backend standing in for "any real MetricsStorage
    implementation" (Redis, Postgres, ...) — proves the API layer only
    depends on the MetricsStorage interface, not on InMemoryMetricsStorage
    specifically."""

    def __init__(self):
        self.events: list[dict] = []

    def add(self, event: dict) -> None:
        self.events.append(event)

    def list(self) -> list[dict]:
        return list(self.events)


def _client_with_storage(storage: MetricsStorage) -> TestClient:
    app = create_app()
    store = LoaderMetricsStore(storage=storage)
    app.dependency_overrides[get_metrics_store] = lambda: store
    return TestClient(app)


def _authenticated_client_with_storage(
    storage: MetricsStorage,
) -> tuple[TestClient, PlatformContainer]:
    app = create_app()
    container = PlatformContainer(bootstrap=PlatformBootstrap())
    store = LoaderMetricsStore(storage=storage)
    app.dependency_overrides[get_platform_container] = lambda: container
    app.dependency_overrides[get_metrics_store] = lambda: store
    return TestClient(app), container


def _login(client: TestClient, email: str) -> str:
    client.post("/api/v1/auth/register", json={"email": email, "password": "123456"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "123456"})
    return response.json()["data"]["token"]


def test_loader_metrics_store_delega_add_para_o_storage_injetado():
    storage = _RecordingStorage()
    store = LoaderMetricsStore(storage=storage)

    store.add({"event": "success", "domain": "cliente.com"})

    assert storage.events == [{"event": "success", "domain": "cliente.com"}]


def test_loader_metrics_store_delega_summary_para_o_storage_injetado():
    storage = _RecordingStorage()
    storage.add({"event": "success", "domain": "cliente.com", "duration": 50})
    store = LoaderMetricsStore(storage=storage)

    summary = store.summary("cliente.com")

    assert summary["total"] == 1
    assert summary["avg_duration"] == 50


def test_endpoint_de_ingestao_usa_o_storage_customizado_injetado():
    """Proves the DI seam works end-to-end through the real HTTP layer, not
    just at the LoaderMetricsStore unit level — a stand-in for swapping in a
    real Redis/Postgres-backed MetricsStorage in production."""
    storage = _RecordingStorage()
    client = _client_with_storage(storage)

    client.post("/api/v1/cdn/metrics", json={"event": "success", "domain": "cliente.com"})

    assert len(storage.events) == 1
    assert storage.events[0]["domain"] == "cliente.com"


def test_endpoint_de_ingestao_preserva_metrica_anterior_do_storage_injetado():
    """The stored event from one request is still there for a later
    request against the same injected storage — the actual, honest version
    of the "persistence" claim: data outlives a single request, as long as
    the process (and its in-memory store) is still alive."""
    storage = _RecordingStorage()
    client = _client_with_storage(storage)

    client.post("/api/v1/cdn/metrics", json={"event": "success", "domain": "cliente.com"})
    client.post("/api/v1/cdn/metrics", json={"event": "error", "domain": "cliente.com"})

    assert len(storage.events) == 2


def test_default_storage_e_in_memory_nao_sobrevive_a_restart():
    """Explicit regression guard against the sprint's own overclaim: the
    *default* storage returned by get_metrics_store() is still
    InMemoryMetricsStorage. Nothing survives an actual process restart yet —
    that requires wiring a real backend, which is future work.
    """
    store = LoaderMetricsStore()

    assert isinstance(store._storage, InMemoryMetricsStorage)


class _AggregatingRecordingStorage(MetricsStorage):
    """Has its own `summary()` (unlike `_RecordingStorage` above) —
    simulates an O(1) aggregated backend (AggregatedRedisMetricsStorage) to
    prove LoaderMetricsStore prefers a storage's own summary() over
    scanning list(), which this fake deliberately doesn't even support."""

    def __init__(self):
        self.summary_calls: list[str | None] = []

    def add(self, event: dict) -> None:
        pass

    def list(self) -> list[dict]:
        raise AssertionError("list() must not be called when storage.summary() exists")

    def summary(self, domain: str | None = None) -> dict:
        self.summary_calls.append(domain)
        return {"total": 42, "success": 42, "error": 0, "avg_duration": 10}


def test_loader_metrics_store_prefere_summary_proprio_do_storage_a_scan():
    storage = _AggregatingRecordingStorage()
    store = LoaderMetricsStore(storage=storage)

    result = store.summary("cliente.com")

    assert result["total"] == 42
    assert storage.summary_calls == ["cliente.com"]


def test_endpoint_de_summary_usa_o_summary_agregado_do_storage_injetado():
    """Same proof as above, through the real HTTP layer: the authenticated,
    unfiltered dashboard query reaches the injected storage's own
    summary(), not a list() scan."""
    storage = _AggregatingRecordingStorage()
    client, _ = _authenticated_client_with_storage(storage)
    token = _login(client, "owner@test.com")

    res = client.get(
        "/api/v1/cdn/metrics/summary", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json()["total"] == 42
    assert storage.summary_calls == [None]


def test_top_domains_retorna_vazio_para_storage_sem_ranking():
    """InMemoryMetricsStorage/RedisMetricsStorage/_RecordingStorage don't
    index by domain — no efficient way to enumerate every domain that ever
    reported an event, so top_domains() degrades to an empty ranking
    instead of attempting an expensive scan just to build one."""
    store = LoaderMetricsStore(storage=_RecordingStorage())

    assert store.top_domains() == []


class _RankingStorage(MetricsStorage):
    """Simulates AggregatedRedisMetricsStorage's top_domains() without
    needing a fake Redis client — proves LoaderMetricsStore.top_domains()
    attaches a health score to whatever its storage ranks."""

    def __init__(self, items: list[dict]):
        self._items = items

    def add(self, event: dict) -> None:
        pass

    def list(self) -> list[dict]:
        return []

    def top_domains(self, limit: int = 10) -> list[dict]:
        return [dict(item) for item in self._items[:limit]]


def test_top_domains_anexa_health_score():
    storage = _RankingStorage(
        [{"domain": "a.com", "total": 10, "error_rate": 0.0, "avg_duration": 50}]
    )
    store = LoaderMetricsStore(storage=storage)

    result = store.top_domains()

    assert result[0]["health"] == 100


def test_top_domains_health_score_penaliza_erro_e_latencia():
    storage = _RankingStorage(
        [{"domain": "a.com", "total": 10, "error_rate": 0.5, "avg_duration": 100}]
    )
    store = LoaderMetricsStore(storage=storage)

    result = store.top_domains()

    # error_penalty = 0.5*100 = 50; latency_penalty = min(100/50, 100) = 2
    assert result[0]["health"] == 48


def test_top_domains_health_score_domino_100_por_cento_erro_nao_quebra():
    """The exact scenario this ranking exists to surface (all-error domain,
    no successful-duration data at all -> avg_duration is None) must not
    crash while computing its health score."""
    storage = _RankingStorage([{"domain": "broken.com", "total": 5, "error_rate": 1.0}])
    store = LoaderMetricsStore(storage=storage)

    result = store.top_domains()

    assert result[0]["health"] == 0


def test_top_domains_health_score_clampado_entre_0_e_100():
    """A malformed/negative self-reported duration (ingestion is
    unauthenticated and doesn't validate it) must not push the score
    outside the 0-100 scale it's supposed to represent."""
    storage = _RankingStorage(
        [{"domain": "a.com", "total": 10, "error_rate": 0.0, "avg_duration": -99999}]
    )
    store = LoaderMetricsStore(storage=storage)

    result = store.top_domains()

    assert 0 <= result[0]["health"] <= 100



# The old test_endpoint_de_dashboard_usa_o_storage_customizado_injetado
# (proving the DI seam for GET /metrics/dashboard) was removed here:
# Sprint 248 changed that endpoint to look up a caller's domains via
# DomainTenantResolver rather than calling store.top_domains() directly, so
# it needs a resolver override too, not just a storage override — that full
# DI-seam-plus-tenant-scoping coverage now lives in
# test_metrics_dashboard.py (e.g. test_dashboard_filtra_por_tenant_sem_vazamento),
# which already exercises a real injected store end-to-end.


# --- Sprint 250: detect_anomalies() -----------------------------------
#
# Real bugs in the spec's own detect_anomalies(): it called
# self.storage.summary_window(domain, 1) directly — wrong attribute name
# (self._storage, not self.storage) AND assumes the configured storage
# always supports time-windowing, which InMemoryMetricsStorage (this app's
# default) does not, so it would raise AttributeError on the very first
# call. Fixed by reusing domains_summary_window(), which already degrades
# gracefully.
#
# The spec's own tests (test_detecta_spike_de_erro / test_sem_anomalia)
# called store.add() in a tight loop and expected a "spike" to be
# detectable — but every add() in a single test run lands in the *same*
# current-hour bucket, so the "last 1h" and "last 24h" windows would see
# identical data (error_spike always 0) regardless of what was added.
# These tests seed older hourly buckets directly (same technique already
# established in test_metrics_storage.py's window tests) to build a real
# healthy-baseline-then-recent-spike scenario.


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def incr(self, key):
        self._values[key] = str(int(self._values.get(key, 0)) + 1)
        return int(self._values[key])

    def incrby(self, key, amount):
        self._values[key] = str(int(self._values.get(key, 0)) + amount)
        return int(self._values[key])

    def incrbyfloat(self, key, amount):
        self._values[key] = str(float(self._values.get(key, 0)) + amount)
        return float(self._values[key])

    def get(self, key):
        return self._values.get(key)

    def expire(self, key, ttl):
        return True

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._values:
            return None

        self._values[key] = value
        return True

    def delete(self, key):
        self._values.pop(key, None)

    def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)

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

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

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
    client._values[f"{prefix}:total"] = str(total)
    client._values[f"{prefix}:success"] = str(total - errors)
    client._values[f"{prefix}:error"] = str(errors)


def test_detect_anomalies_storage_sem_janela_nao_quebra():
    """The actual crash the spec's own code would hit: InMemoryMetricsStorage
    (this app's default) has no summary_window() at all."""
    store = LoaderMetricsStore()

    store.add({"domain": "a.com", "event": "error"})

    assert store.detect_anomalies(["a.com"]) == []


def test_detect_anomalies_sem_dados_nao_gera_alerta():
    storage = AggregatedRedisMetricsStorage(_FakeRedisClient())
    store = LoaderMetricsStore(storage=storage)

    assert store.detect_anomalies(["never-seen.com"]) == []


def test_detect_anomalies_sem_spike_nao_gera_alerta():
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "success", "duration": 100})

    assert store.detect_anomalies(["a.com"]) == []


def test_detect_anomalies_detecta_spike_de_erro_recente():
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    store = LoaderMetricsStore(storage=storage)

    # Healthy history: 23 prior hours, 50 events/hour, no errors.
    for hours_ago in range(1, 24):
        _seed_bucket(client, "a.com", hours_ago, total=50, errors=0)

    # Real spike in the current hour, via add() — 10 successes, 90 errors.
    for _ in range(10):
        store.add({"domain": "a.com", "event": "success", "duration": 100})
    for _ in range(90):
        store.add({"domain": "a.com", "event": "error"})

    alerts = store.detect_anomalies(["a.com"])

    assert len(alerts) == 1
    assert alerts[0]["domain"] == "a.com"
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["error_spike"] > 0.2


def test_detect_anomalies_spike_pequeno_abaixo_do_threshold_nao_alerta():
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    store = LoaderMetricsStore(storage=storage)

    for hours_ago in range(1, 24):
        _seed_bucket(client, "a.com", hours_ago, total=100, errors=0)

    for _ in range(90):
        store.add({"domain": "a.com", "event": "success", "duration": 100})
    for _ in range(10):
        store.add({"domain": "a.com", "event": "error"})

    assert store.detect_anomalies(["a.com"]) == []


def test_detect_anomalies_isola_dominios_diferentes():
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    store = LoaderMetricsStore(storage=storage)

    for hours_ago in range(1, 24):
        _seed_bucket(client, "healthy.com", hours_ago, total=50, errors=0)
        _seed_bucket(client, "broken.com", hours_ago, total=50, errors=0)

    for _ in range(50):
        store.add({"domain": "healthy.com", "event": "success", "duration": 100})
    for _ in range(50):
        store.add({"domain": "broken.com", "event": "error"})

    alerts = store.detect_anomalies(["healthy.com", "broken.com"])

    assert [a["domain"] for a in alerts] == ["broken.com"]


def test_severity_limites():
    """Sprint 251's _severity() signature grew from 2 args (error_spike,
    latency_spike) to 5 (+ volume, current_error, baseline_error) — this
    replaces the old Sprint 250 version of this test, which would now fail
    with a TypeError on the old 2-arg calls."""
    sev = LoaderMetricsStore._severity

    # Below the volume floor: always low, no matter how extreme the rates.
    assert sev(0.9, 0, volume=10, current_error=1.0, baseline_error=0.0) == "low"

    # Absolute floor (current_error > 0.3) drives critical/high.
    assert sev(0.6, 0, volume=100, current_error=0.6, baseline_error=0.05) == "critical"
    assert sev(0.35, 0, volume=100, current_error=0.35, baseline_error=0.05) == "high"

    # Relative floor (current_error > 2x baseline) when baseline is high
    # enough for 2x to exceed the 0.3 absolute floor.
    assert sev(0.25, 0, volume=100, current_error=0.45, baseline_error=0.2) == "high"

    # Latency-only spike, error rate flat.
    assert sev(0.0, 350, volume=100, current_error=0.05, baseline_error=0.05) == "high"

    # error_spike alone, current_error still under the high threshold.
    assert sev(0.25, 0, volume=100, current_error=0.28, baseline_error=0.03) == "medium"

    # Nothing crosses any threshold.
    assert sev(0.05, 10, volume=100, current_error=0.08, baseline_error=0.03) == "low"


def test_detect_anomalies_baseline_exclui_a_hora_atual():
    """Sprint 251's actual baseline fix: a spike this hour must not get
    diluted into its own 24h baseline the way Sprint 250's version did
    (offset=0 for both windows there)."""
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    store = LoaderMetricsStore(storage=storage)

    # A single, clean, healthy hour 5 hours ago — seeded directly since
    # add() always targets the current hour.
    old_bucket = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y%m%d%H")
    prefix = f"metrics:a.com:bucket:{old_bucket}"
    client._values[f"{prefix}:total"] = "100"
    client._values[f"{prefix}:success"] = "100"
    client._values[f"{prefix}:error"] = "0"

    # Total failure in the current hour.
    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    alerts = store.detect_anomalies(["a.com"])

    assert len(alerts) == 1
    assert alerts[0]["baseline"]["total"] == 100
    assert alerts[0]["baseline"]["error"] == 0
    assert alerts[0]["current"]["total"] == 50
    assert alerts[0]["current"]["error"] == 50


def test_detect_anomalies_dominio_novo_sem_baseline_nao_quebra():
    """A domain with traffic in the last hour but none at all in the prior
    24h (e.g. a brand-new domain) must not crash: baseline["error_rate"] is
    None with zero baseline total, and error_spike = current - None would
    raise TypeError without this guard."""
    storage = AggregatedRedisMetricsStorage(_FakeRedisClient())
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "brand-new.com", "event": "error"})

    assert store.detect_anomalies(["brand-new.com"]) == []


def test_detect_anomalies_debounce_impede_alerta_repetido():
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    store = LoaderMetricsStore(storage=storage)

    old_bucket = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y%m%d%H")
    prefix = f"metrics:a.com:bucket:{old_bucket}"
    client._values[f"{prefix}:total"] = "100"
    client._values[f"{prefix}:success"] = "100"

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    alerts1 = store.detect_anomalies(["a.com"])
    alerts2 = store.detect_anomalies(["a.com"])

    assert len(alerts1) == 1
    assert len(alerts2) == 0


def test_detect_anomalies_storage_sem_debounce_nunca_suprime():
    """A storage with no should_emit_alert() capability (any custom
    MetricsStorage that doesn't implement it) must never suppress an alert
    — debounce is optional, not required."""

    class _NoDebounceStorage(_RecordingStorage):
        def summary_window(self, domain, hours, offset=0):
            if offset == 0:
                return {
                    "total": 50,
                    "success": 0,
                    "error": 50,
                    "error_rate": 1.0,
                    "avg_duration": None,
                }
            return {
                "total": 100,
                "success": 100,
                "error": 0,
                "error_rate": 0.0,
                "avg_duration": 100,
            }

    store = LoaderMetricsStore(storage=_NoDebounceStorage())

    alerts1 = store.detect_anomalies(["a.com"])
    alerts2 = store.detect_anomalies(["a.com"])

    assert len(alerts1) == 1
    assert len(alerts2) == 1


# --- Sprint 252: incident tracking + webhook integration ---------------


def _healthy_baseline(client: _FakeRedisClient, domain: str, total: int = 100) -> None:
    for hours_ago in range(1, 24):
        _seed_bucket(client, domain, hours_ago, total=total, errors=0)


class _RecordingWebhook:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, payload: dict) -> None:
        self.sent.append(payload)


class _RecordingBackgroundTasks:
    """Stand-in for FastAPI's BackgroundTasks — records scheduled calls
    instead of a real deferred-execution mechanism, enough to prove
    detect_anomalies() defers the webhook rather than calling it inline."""

    def __init__(self):
        self.tasks: list[tuple] = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))


def test_detect_anomalies_primeiro_alerta_e_open_e_dispara_webhook():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    webhook = _RecordingWebhook()
    storage = AggregatedRedisMetricsStorage(
        client, incident_manager=IncidentManager(client), webhook=webhook
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    alerts = store.detect_anomalies(["a.com"])

    assert alerts[0]["incident"]["status"] == "open"
    assert len(webhook.sent) == 1
    assert webhook.sent[0]["domain"] == "a.com"


def test_detect_anomalies_alerta_repetido_e_ongoing_e_nao_dispara_webhook_de_novo():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    webhook = _RecordingWebhook()
    storage = AggregatedRedisMetricsStorage(
        client, incident_manager=IncidentManager(client), webhook=webhook
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"])
    second = store.detect_anomalies(["a.com"])

    assert second[0]["incident"]["status"] == "ongoing"
    assert second[0]["incident"]["incident"]["count"] == 2
    assert len(webhook.sent) == 1


def test_detect_anomalies_com_incident_manager_nao_esconde_alerta_continuo():
    """Unlike Sprint 251's response-level debounce, an ongoing incident
    must stay visible on every call — this is a status view, not a
    one-shot notification feed. Only the webhook is limited to firing once
    (proven by the tests above)."""
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    alerts1 = store.detect_anomalies(["a.com"])
    alerts2 = store.detect_anomalies(["a.com"])

    assert len(alerts1) == 1
    assert len(alerts2) == 1


def test_detect_anomalies_webhook_usa_background_tasks_quando_fornecido():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    webhook = _RecordingWebhook()
    storage = AggregatedRedisMetricsStorage(
        client, incident_manager=IncidentManager(client), webhook=webhook
    )
    store = LoaderMetricsStore(storage=storage)
    background_tasks = _RecordingBackgroundTasks()

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"], background_tasks=background_tasks)

    # Scheduled, not called inline: the request-handling path must not
    # block on the webhook's own (up to several-second) HTTP timeout.
    assert webhook.sent == []
    assert len(background_tasks.tasks) == 1
    func, args, _ = background_tasks.tasks[0]
    assert func == webhook.send
    assert args[0]["domain"] == "a.com"


def test_detect_anomalies_severidade_baixa_resolve_incidente_aberto():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})
    store.detect_anomalies(["a.com"])

    # Traffic normalizes: fresh healthy events land in the same current
    # hour, diluting it back below every anomaly threshold.
    for _ in range(500):
        store.add({"domain": "a.com", "event": "success", "duration": 10})

    alerts = store.detect_anomalies(["a.com"])

    assert alerts == []
    history = store.get_incident_history(["a.com"])
    assert len(history) == 1
    assert history[0]["domain"] == "a.com"


def test_detect_anomalies_tipo_error_para_taxa_de_erro_alta():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    alerts = store.detect_anomalies(["a.com"])

    assert alerts[0]["type"] == "error"


def test_get_incident_history_vazio_sem_incident_manager():
    store = LoaderMetricsStore()

    assert store.get_incident_history(["a.com"]) == []


def test_get_incident_history_isolado_por_dominio():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.resolve("a.com", "error")
    manager.open_or_update("b.com", "error", {"severity": "high"})
    manager.resolve("b.com", "error")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=manager)
    store = LoaderMetricsStore(storage=storage)

    history_a_only = store.get_incident_history(["a.com"])

    assert len(history_a_only) == 1
    assert history_a_only[0]["domain"] == "a.com"


# --- Sprint 253: active incidents + has_incident_tracking() ------------


def test_has_incident_tracking_false_por_padrao():
    store = LoaderMetricsStore()

    assert store.has_incident_tracking() is False


def test_has_incident_tracking_true_com_incident_manager():
    client = _FakeRedisClient()
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    assert store.has_incident_tracking() is True


def test_get_active_incidents_vazio_sem_incident_manager():
    store = LoaderMetricsStore()

    assert store.get_active_incidents(["a.com"]) == []


def test_get_active_incidents_reflete_estado_persistido():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})
    store.detect_anomalies(["a.com"])

    active = store.get_active_incidents(["a.com"])

    assert len(active) == 1
    assert active[0]["domain"] == "a.com"
    assert active[0]["type"] == "error"


def test_get_active_incidents_vazio_apos_resolucao():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})
    store.detect_anomalies(["a.com"])

    for _ in range(500):
        store.add({"domain": "a.com", "event": "success", "duration": 10})
    store.detect_anomalies(["a.com"])

    assert store.get_active_incidents(["a.com"]) == []


def test_get_active_incidents_isolado_por_dominio():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "high"})
    manager.open_or_update("b.com", "error", {"severity": "critical"})
    storage = AggregatedRedisMetricsStorage(client, incident_manager=manager)
    store = LoaderMetricsStore(storage=storage)

    only_a = store.get_active_incidents(["a.com"])

    assert len(only_a) == 1
    assert only_a[0]["domain"] == "a.com"


def test_get_active_incidents_ordenado_por_severidade():
    client = _FakeRedisClient()
    manager = IncidentManager(client)
    manager.open_or_update("a.com", "error", {"severity": "medium"})
    manager.open_or_update("b.com", "error", {"severity": "critical"})
    storage = AggregatedRedisMetricsStorage(client, incident_manager=manager)
    store = LoaderMetricsStore(storage=storage)

    active = store.get_active_incidents(["a.com", "b.com"])

    assert [item["domain"] for item in active] == ["b.com", "a.com"]


# --- Sprint 256: webhook queue + retry ----------------------------------


class _AlwaysSucceedsClient:
    def __init__(self, url, timeout_seconds=2.0):
        self.url = url

    def send(self, payload: dict) -> bool:
        return True


def test_send_webhook_prefere_a_fila_quando_configurada():
    """Storages with a webhook_queue take the new queue+retry path even if
    a plain `webhook` (Sprint 252) is also set — full backward
    compatibility for storages configured only the old way is covered by
    test_detect_anomalies_primeiro_alerta_e_open_e_dispara_webhook above,
    which never sets webhook_queue at all."""
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    plain_webhook = _RecordingWebhook()
    queue = WebhookQueue(client)
    queue.set_url("https://hooks.example.com/webhook")
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)
    storage = AggregatedRedisMetricsStorage(
        client,
        incident_manager=IncidentManager(client),
        webhook=plain_webhook,
        webhook_queue=queue,
        webhook_worker=worker,
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"])

    # Delivered via the queue+worker path (drained synchronously since no
    # background_tasks was passed), not the old direct-send fallback.
    assert plain_webhook.sent == []
    assert queue.queue_size() == 0


def test_send_webhook_via_fila_agenda_drain_em_background_tasks():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    queue = WebhookQueue(client)
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)
    storage = AggregatedRedisMetricsStorage(
        client,
        incident_manager=IncidentManager(client),
        webhook_queue=queue,
        webhook_worker=worker,
    )
    store = LoaderMetricsStore(storage=storage)
    background_tasks = _RecordingBackgroundTasks()

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"], background_tasks=background_tasks)

    # Enqueued immediately (not deferred — persistence must happen inline,
    # only *delivery* is deferred), and a drain is scheduled rather than
    # run inline.
    assert queue.queue_size() == 1
    assert len(background_tasks.tasks) == 1
    func, _, _ = background_tasks.tasks[0]
    assert func == worker.process


def test_send_webhook_falha_de_entrega_nao_perde_o_alerta():
    """The alert survives a failed delivery attempt — it's requeued, not
    dropped, unlike the original spec's silent-drop-on-exhaustion bug."""

    class _AlwaysFailsClient:
        def __init__(self, url, timeout_seconds=2.0):
            pass

        def send(self, payload):
            return False

    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    queue = WebhookQueue(client)
    queue.set_url("https://hooks.example.com/webhook")
    worker = WebhookWorker(queue, client_factory=_AlwaysFailsClient)
    storage = AggregatedRedisMetricsStorage(
        client,
        incident_manager=IncidentManager(client),
        webhook_queue=queue,
        webhook_worker=worker,
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"])

    assert queue.queue_size() == 1


def test_set_webhook_url_false_sem_webhook_queue_configurado():
    store = LoaderMetricsStore()

    assert store.set_webhook_url("https://hooks.example.com/webhook") is False


def test_set_webhook_url_true_e_efetivo_com_webhook_queue():
    client = _FakeRedisClient()
    queue = WebhookQueue(client)
    storage = AggregatedRedisMetricsStorage(client, webhook_queue=queue)
    store = LoaderMetricsStore(storage=storage)

    assert store.set_webhook_url("https://hooks.example.com/webhook") is True
    assert queue.get_url() == "https://hooks.example.com/webhook"


def test_webhook_queue_status_sem_webhook_queue():
    store = LoaderMetricsStore()

    assert store.webhook_queue_status() == {
        "configured": False,
        "queue_size": 0,
        "failed_count": 0,
    }


def test_webhook_queue_status_reflete_estado_real():
    client = _FakeRedisClient()
    queue = WebhookQueue(client)
    queue.enqueue({"domain": "a.com"})
    queue.enqueue({"domain": "b.com"})
    storage = AggregatedRedisMetricsStorage(client, webhook_queue=queue)
    store = LoaderMetricsStore(storage=storage)

    status = store.webhook_queue_status()

    assert status == {"configured": True, "queue_size": 2, "failed_count": 0}


def test_process_webhook_queue_none_sem_webhook_worker():
    store = LoaderMetricsStore()

    assert store.process_webhook_queue() is None


def test_process_webhook_queue_drena_com_webhook_worker():
    client = _FakeRedisClient()
    queue = WebhookQueue(client)
    queue.set_url("https://hooks.example.com/webhook")
    queue.enqueue({"domain": "a.com"})
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)
    storage = AggregatedRedisMetricsStorage(client, webhook_queue=queue, webhook_worker=worker)
    store = LoaderMetricsStore(storage=storage)

    result = store.process_webhook_queue()

    assert result == {"sent": 1, "failed": 0, "processed": 1}
    assert queue.queue_size() == 0


# --- Sprint 270: usage tracking inside _send_webhook() -------------------


def test_send_webhook_registra_uso_quando_tenant_id_resolvido():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    usage_tracker = UsageTracker(client)
    storage = AggregatedRedisMetricsStorage(
        client, incident_manager=IncidentManager(client), usage_tracker=usage_tracker
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"], resolve_tenant=lambda domain: "tenant-a")

    assert usage_tracker.get("tenant-a", "alerts_sent") == 1


def test_send_webhook_sem_tenant_id_nao_registra_uso():
    """No resolve_tenant callable (the common case for most callers) ->
    tenant_id stays None -> nothing to attribute usage to, no crash."""
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    usage_tracker = UsageTracker(client)
    storage = AggregatedRedisMetricsStorage(
        client, incident_manager=IncidentManager(client), usage_tracker=usage_tracker
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"])

    assert usage_tracker.get("tenant-a", "alerts_sent") == 0


def test_send_webhook_dominio_silenciado_nao_registra_uso():
    """Usage tracking happens after the silence/cooldown gate -- a
    deliberately silenced domain generates no billable notification."""
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    usage_tracker = UsageTracker(client)
    controls = AlertControlManager(client)
    controls.silence("a.com", 3600)
    storage = AggregatedRedisMetricsStorage(
        client,
        incident_manager=IncidentManager(client),
        usage_tracker=usage_tracker,
        alert_controls=controls,
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    store.detect_anomalies(["a.com"], resolve_tenant=lambda domain: "tenant-a")

    assert usage_tracker.get("tenant-a", "alerts_sent") == 0


def test_send_webhook_ainda_registra_uso_mesmo_rate_limitado():
    """Usage is meant for future overage billing -- volume that exceeded
    the rate limit is exactly the volume that matters, so it must still
    be counted even when the alert itself gets diverted to the digest."""
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    usage_tracker = UsageTracker(client)
    rate_limiter = AlertRateLimiter(client)
    storage = AggregatedRedisMetricsStorage(
        client,
        incident_manager=IncidentManager(client),
        usage_tracker=usage_tracker,
        rate_limiter=rate_limiter,
    )
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    def get_alert_limit(tenant_id):
        return 0  # always rate-limited

    store.detect_anomalies(
        ["a.com"], resolve_tenant=lambda domain: "tenant-a", get_alert_limit=get_alert_limit
    )

    assert usage_tracker.get("tenant-a", "alerts_sent") == 1


def test_send_webhook_sem_usage_tracker_nao_quebra():
    client = _FakeRedisClient()
    _healthy_baseline(client, "a.com")
    storage = AggregatedRedisMetricsStorage(client, incident_manager=IncidentManager(client))
    store = LoaderMetricsStore(storage=storage)

    for _ in range(50):
        store.add({"domain": "a.com", "event": "error"})

    alerts = store.detect_anomalies(["a.com"], resolve_tenant=lambda domain: "tenant-a")

    assert len(alerts) == 1
