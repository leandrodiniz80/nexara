import fnmatch
from datetime import datetime, timedelta, timezone

import pytest

from app.platform.metrics.metrics_storage import (
    AggregatedRedisMetricsStorage,
    InMemoryMetricsStorage,
    MetricsStorage,
    RedisMetricsStorage,
)


def test_metrics_storage_base_add_e_no_op():
    storage = MetricsStorage()

    storage.add({"event": "success"})

    assert storage.list() == []


def test_metrics_storage_base_list_retorna_vazio():
    storage = MetricsStorage()

    assert storage.list() == []


def test_in_memory_add_e_list_round_trip():
    storage = InMemoryMetricsStorage()

    storage.add({"event": "success", "domain": "a.com"})

    assert storage.list() == [{"event": "success", "domain": "a.com"}]


def test_in_memory_respeita_maxlen():
    storage = InMemoryMetricsStorage(maxlen=3)

    for i in range(5):
        storage.add({"event": "success", "i": i})

    events = storage.list()
    assert len(events) == 3
    assert [e["i"] for e in events] == [2, 3, 4]


def test_in_memory_isolado_entre_instancias():
    storage_a = InMemoryMetricsStorage()
    storage_b = InMemoryMetricsStorage()

    storage_a.add({"event": "success"})

    assert storage_b.list() == []


class _FakeRedisClient:
    """In-process double for redis.Redis — just enough of .rpush()/.lrange()/
    .ltrim()/.expire() to exercise RedisMetricsStorage without a real Redis
    server."""

    def __init__(self):
        self._lists: dict[str, list[str]] = {}
        self._ttls: dict[str, int] = {}

    def rpush(self, key, value):
        self._lists.setdefault(key, []).append(value)

    def lrange(self, key, start, end):
        values = self._lists.get(key, [])
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    def ltrim(self, key, start, end):
        values = self._lists.get(key, [])
        self._lists[key] = values[start:] if end == -1 else values[start : end + 1]

    def expire(self, key, ttl):
        self._ttls[key] = ttl


def test_redis_storage_add_e_list_round_trip():
    client = _FakeRedisClient()
    storage = RedisMetricsStorage(client)

    storage.add({"event": "success", "domain": "cliente.com"})

    assert storage.list() == [{"event": "success", "domain": "cliente.com"}]


def test_redis_storage_serializa_como_json_no_client():
    client = _FakeRedisClient()
    storage = RedisMetricsStorage(client)

    storage.add({"event": "success"})

    raw = client._lists["loader_metrics"][0]
    assert isinstance(raw, str)
    assert '"event": "success"' in raw


def test_redis_storage_usa_chave_padrao_loader_metrics():
    client = _FakeRedisClient()
    storage = RedisMetricsStorage(client)

    storage.add({"event": "success"})

    assert "loader_metrics" in client._lists


def test_redis_storage_usa_chave_customizada():
    client = _FakeRedisClient()
    storage = RedisMetricsStorage(client, key="custom_key")

    storage.add({"event": "success"})

    assert "custom_key" in client._lists
    assert "loader_metrics" not in client._lists


def test_redis_storage_isolado_por_chave_no_mesmo_client():
    client = _FakeRedisClient()
    storage_a = RedisMetricsStorage(client, key="tenant-a")
    storage_b = RedisMetricsStorage(client, key="tenant-b")

    storage_a.add({"event": "success", "domain": "a.com"})

    assert storage_a.list() == [{"event": "success", "domain": "a.com"}]
    assert storage_b.list() == []


def test_redis_storage_seta_ttl_a_cada_escrita():
    client = _FakeRedisClient()
    storage = RedisMetricsStorage(client, ttl_seconds=3600)

    storage.add({"event": "success"})

    assert client._ttls["loader_metrics"] == 3600


def test_redis_storage_respeita_max_len_via_ltrim():
    """TTL alone never bounds memory under continuous traffic — it just
    keeps getting pushed back on every write. LTRIM is what actually caps
    the list size, regardless of how much traffic keeps flowing."""
    client = _FakeRedisClient()
    storage = RedisMetricsStorage(client, max_len=3)

    for i in range(5):
        storage.add({"event": "success", "i": i})

    events = storage.list()
    assert len(events) == 3
    assert [e["i"] for e in events] == [2, 3, 4]


class _FakeAggregatingRedisClient:
    """In-process double for redis.Redis supporting the subset of the API
    AggregatedRedisMetricsStorage needs: incr/incrbyfloat/get/expire/
    scan_iter, plus a real queuing pipeline() — commands queue on the
    pipeline object and only run (against this client's own state, so
    later reads see them) when execute() is called, returning their
    results in call order. A "pipeline() returns self, execute() is a
    no-op" fake would work for writes (nothing here reads their return
    values) but can't support summary_window()'s pipelined get() calls at
    all, since nothing would batch their results into a return value.

    scan_iter (not keys()): real Redis's KEYS command blocks the whole
    instance while it walks the entire keyspace — this fake mirrors the
    non-blocking, cursor-based API (`scan_iter(match=pattern)`) that
    AggregatedRedisMetricsStorage.top_domains() actually calls.
    """

    def __init__(self):
        self._values: dict[str, str] = {}

    def incr(self, key):
        self._values[key] = str(int(self._values.get(key, 0)) + 1)
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

    def scan_iter(self, match=None):
        pattern = match or "*"
        return iter(k for k in self._values if fnmatch.fnmatch(k, pattern))

    def pipeline(self):
        return _FakeRedisPipeline(self)


class _FakeRedisPipeline:
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


def test_aggregated_redis_storage_total_e_o1_nao_scan():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    for _ in range(1000):
        storage.add({"domain": "a.com", "event": "success", "duration": 100})

    summary = storage.summary("a.com")

    assert summary["total"] == 1000
    assert summary["success"] == 1000
    assert summary["avg_duration"] == 100


def test_aggregated_redis_storage_conta_erros_e_calcula_error_rate():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})
    storage.add({"domain": "a.com", "event": "error"})

    summary = storage.summary("a.com")

    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["error"] == 1
    assert summary["error_rate"] == 0.5


def test_aggregated_redis_storage_avg_duration_ignora_eventos_de_erro():
    """Matches the scan-based summary's existing semantics (LoaderMetricsStore
    ._summary_from_events): avg_duration is the mean duration of
    *successful* events only, even if an error event also reports one."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})
    storage.add({"domain": "a.com", "event": "error", "duration": 9999})

    assert storage.summary("a.com")["avg_duration"] == 100


def test_aggregated_redis_storage_isolado_por_dominio():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})
    storage.add({"domain": "b.com", "event": "error"})

    assert storage.summary("a.com")["total"] == 1
    assert storage.summary("a.com")["error"] == 0
    assert storage.summary("b.com")["total"] == 1
    assert storage.summary("b.com")["error"] == 1


def test_aggregated_redis_storage_agregado_global_sem_filtro_de_dominio():
    """The critical gap the sprint's own spec left unfixed: its
    `summary(self, domain: str)` had no default and no way to aggregate
    across all domains at all, which /cdn/metrics/summary already supports
    and is already tested (the unfiltered dashboard view). A dedicated
    global scope keeps that working with O(1) counters too."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})
    storage.add({"domain": "b.com", "event": "error"})

    summary = storage.summary(None)

    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["error"] == 1
    assert summary["domain"] is None


def test_aggregated_redis_storage_summary_vazio_sem_dados():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    summary = storage.summary("never-seen.com")

    assert summary["total"] == 0
    assert summary["avg_duration"] is None
    assert summary["error_rate"] is None


def test_aggregated_redis_storage_list_nao_suportado():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    with pytest.raises(NotImplementedError):
        storage.list()


def test_top_domains_ranking_por_volume():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    for _ in range(100):
        storage.add({"domain": "a.com", "event": "success", "duration": 100})
    for _ in range(50):
        storage.add({"domain": "b.com", "event": "success", "duration": 100})

    result = storage.top_domains(2)

    assert result[0]["domain"] == "a.com"
    assert result[0]["total"] == 100
    assert result[1]["domain"] == "b.com"
    assert result[1]["total"] == 50


def test_top_domains_respeita_limit():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    for domain in ["a.com", "b.com", "c.com"]:
        storage.add({"domain": domain, "event": "success", "duration": 10})

    assert len(storage.top_domains(limit=2)) == 2


def test_top_domains_nao_inclui_o_escopo_global():
    """The critical bug in the spec's own top_domains(): the global
    aggregate counter lives under the same "metrics:*:total" keyspace and,
    unfiltered, would rank #1 every time (it's the sum of every domain) —
    "__global__" must never appear as a ranked domain."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 10})

    domains = [item["domain"] for item in storage.top_domains(10)]

    assert "__global__" not in domains
    assert domains == ["a.com"]


def test_top_domains_nao_conta_domino_duas_vezes_por_causa_dos_buckets():
    """Sprint 249 regression: `add()` now also writes hourly bucket keys
    under the same "metrics:{domain}:bucket:{hour}:total" shape, which a
    glob like "metrics:*:total" also matches ("*" spans ":" in both
    fnmatch and real Redis glob syntax) — top_domains() must not let those
    inflate a domain's ranking entry or appear as separate pseudo-domains.
    """
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 10})

    result = storage.top_domains(10)

    assert len(result) == 1
    assert result[0]["domain"] == "a.com"
    assert result[0]["total"] == 1


def test_top_domains_sem_dados_retorna_lista_vazia():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    assert storage.top_domains() == []


def test_top_domains_dominio_100_por_cento_erro_nao_quebra():
    """The exact scenario the ranking exists to surface (a domain with
    nothing but failures) must not crash computing its own ranking entry —
    avg_duration is None here since there's no successful-duration data at
    all, and the reader must handle that."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "broken.com", "event": "error"})

    result = storage.top_domains(10)

    assert result[0]["domain"] == "broken.com"
    assert result[0]["avg_duration"] is None
    assert result[0]["error_rate"] == 1.0


def test_add_grava_bucket_horario_para_o_dominio():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})

    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    assert client._values[f"metrics:a.com:bucket:{bucket}:total"] == "1"
    assert client._values[f"metrics:a.com:bucket:{bucket}:success"] == "1"


def test_add_seta_ttl_em_todos_os_contadores_do_bucket():
    """Every bucket key add() writes to (total, success,
    success_duration_sum, success_duration_count) must get an expire() —
    the earlier bug this guards against only expired total/success/error,
    leaking the duration-sum/-count keys forever."""
    client = _FakeAggregatingRedisClient()
    expired_keys = []
    original_expire = client.expire
    client.expire = lambda key, ttl: expired_keys.append(key) or original_expire(key, ttl)
    storage = AggregatedRedisMetricsStorage(client, bucket_ttl_seconds=3600)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})

    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    assert f"metrics:a.com:bucket:{bucket}:total" in expired_keys
    assert f"metrics:a.com:bucket:{bucket}:success" in expired_keys
    assert f"metrics:a.com:bucket:{bucket}:success_duration_sum" in expired_keys
    assert f"metrics:a.com:bucket:{bucket}:success_duration_count" in expired_keys


def test_add_nao_grava_bucket_para_escopo_global():
    """Nothing currently reads a platform-wide windowed summary — writing
    (and expiring) a global bucket on every event would be pure cost with
    no reader."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})

    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
    assert f"metrics:__global__:bucket:{bucket}:total" not in client._values


def test_summary_window_ultimas_24h():
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    storage.add({"domain": "a.com", "event": "success", "duration": 100})

    result = storage.summary_window("a.com", hours=24)

    assert result["total"] == 1
    assert result["success"] == 1
    assert result["error"] == 0
    assert result["avg_duration"] == 100


def test_summary_window_ignora_eventos_fora_da_janela():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    old_bucket = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y%m%d%H")
    client._values[f"metrics:a.com:bucket:{old_bucket}:total"] = "5"
    client._values[f"metrics:a.com:bucket:{old_bucket}:success"] = "5"

    storage.add({"domain": "a.com", "event": "success", "duration": 100})

    result = storage.summary_window("a.com", hours=24)

    # Only the just-added event (current hour) counts — the 48h-old bucket
    # falls outside a 24h window.
    assert result["total"] == 1


def test_summary_window_ignora_duracao_de_eventos_de_erro():
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    storage.add({"domain": "a.com", "event": "success", "duration": 100})
    storage.add({"domain": "a.com", "event": "error", "duration": 9999})

    result = storage.summary_window("a.com", hours=24)

    assert result["total"] == 2
    assert result["error"] == 1
    assert result["avg_duration"] == 100


def test_summary_window_dominio_sem_dados_retorna_zero():
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    result = storage.summary_window("never-seen.com", hours=24)

    assert result["total"] == 0
    assert result["avg_duration"] is None
    assert result["error_rate"] is None


def test_summary_window_hours_absurdo_nao_quebra():
    """A caller-supplied `hours` isn't otherwise bounded (see cdn.py's own
    clamp) — this is the storage-level defense-in-depth backstop."""
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    result = storage.summary_window("a.com", hours=999_999)

    assert result["total"] == 0


def test_summary_window_usa_pipeline_para_leituras():
    """A sequential get() per bucket per metric would mean
    hours * len(_WINDOW_METRICS) individual round trips for one domain —
    confirms reads are batched through a single pipeline instead."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)
    storage.add({"domain": "a.com", "event": "success", "duration": 100})

    original_pipeline = client.pipeline
    calls = []
    client.pipeline = lambda: (calls.append(1), original_pipeline())[1]

    storage.summary_window("a.com", hours=24)

    assert len(calls) == 1


def test_summary_window_offset_exclui_a_hora_atual():
    """Sprint 251's baseline fix: offset=1 must exclude the current hour's
    bucket entirely — the whole point is measuring a domain against clean
    prior data, not data that includes the very hour being compared."""
    client = _FakeAggregatingRedisClient()
    storage = AggregatedRedisMetricsStorage(client)

    # Current hour: a spike, via a real add() call.
    storage.add({"domain": "a.com", "event": "error"})

    # An older hour, seeded directly (add() always targets "now").
    old_bucket = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y%m%d%H")
    client._values[f"metrics:a.com:bucket:{old_bucket}:total"] = "10"
    client._values[f"metrics:a.com:bucket:{old_bucket}:success"] = "10"

    current = storage.summary_window("a.com", hours=1, offset=0)
    baseline = storage.summary_window("a.com", hours=24, offset=1)

    assert current["total"] == 1
    assert current["error"] == 1
    assert baseline["total"] == 10
    assert baseline["error"] == 0


def test_should_emit_alert_permite_na_primeira_chamada():
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    assert storage.should_emit_alert("a.com:critical") is True


def test_should_emit_alert_bloqueia_repeticao_dentro_da_janela():
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    first = storage.should_emit_alert("a.com:critical", window_seconds=300)
    second = storage.should_emit_alert("a.com:critical", window_seconds=300)

    assert first is True
    assert second is False


def test_should_emit_alert_chaves_diferentes_sao_independentes():
    """Debounce keyed by severity too, not just domain — an escalation from
    one severity tier to another must not be swallowed by an already-open
    debounce window from the earlier, less severe alert."""
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    storage.should_emit_alert("a.com:medium")

    assert storage.should_emit_alert("a.com:critical") is True


def test_should_emit_alert_usa_set_nx_ex_atomico_nao_setnx_mais_expire():
    """A separate SETNX + EXPIRE has a real race: a crash between the two
    calls leaves the debounce key with no TTL, permanently suppressing that
    key's alerts. Confirms the single atomic call this guards against that:
    the debounce key must already carry a TTL right after the first call,
    not depend on a second call ever happening."""

    class _NoExpireCallClient(_FakeAggregatingRedisClient):
        def expire(self, key, ttl):
            raise AssertionError("expire() must not be called by should_emit_alert()")

    storage = AggregatedRedisMetricsStorage(_NoExpireCallClient())

    assert storage.should_emit_alert("a.com:critical") is True


def test_should_emit_alert_fail_open_quando_redis_falha():
    class _FailingClient:
        def set(self, *args, **kwargs):
            raise ConnectionError("redis down")

    storage = AggregatedRedisMetricsStorage(_FailingClient())

    assert storage.should_emit_alert("a.com:critical") is True


def test_incident_manager_e_webhook_sao_none_por_padrao():
    """Sprint 252's optional capabilities default to unset — a plain
    AggregatedRedisMetricsStorage(client) call, exactly as every prior
    sprint's tests already construct one, must not suddenly gain incident
    tracking or webhook dispatch it never asked for."""
    storage = AggregatedRedisMetricsStorage(_FakeAggregatingRedisClient())

    assert storage.incident_manager is None
    assert storage.webhook is None
    assert storage.webhook_queue is None
    assert storage.webhook_worker is None


def test_incident_manager_e_webhook_sao_atribuidos_via_construtor():
    """Not bolted on after construction (storage.incident_manager = X) —
    real constructor parameters, part of the class's own declared
    interface."""

    class _Sentinel:
        pass

    incident_manager = _Sentinel()
    webhook = _Sentinel()
    webhook_queue = _Sentinel()
    webhook_worker = _Sentinel()

    storage = AggregatedRedisMetricsStorage(
        _FakeAggregatingRedisClient(),
        incident_manager=incident_manager,
        webhook=webhook,
        webhook_queue=webhook_queue,
        webhook_worker=webhook_worker,
    )

    assert storage.incident_manager is incident_manager
    assert storage.webhook is webhook
    assert storage.webhook_queue is webhook_queue
    assert storage.webhook_worker is webhook_worker
