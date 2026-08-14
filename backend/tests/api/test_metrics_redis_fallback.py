"""Tests for _create_storage()'s Redis wiring and fallback behavior.

The sprint's own claim ("Falha total se Redis cair -> Corrigido: fallback
automático") had zero test coverage for the actual failure case — its one
test only checked "REDIS_URL not set at all", never "REDIS_URL set but the
connection fails", which is the realistic production scenario the claim is
actually about. Covered here via a monkeypatched `redis.Redis.from_url`
(fast and deterministic — no real network I/O, no dependency on an actual
Redis server being reachable or unreachable in this environment).
"""

import redis

from app.api.dependencies.metrics import _create_storage
from app.platform.metrics.metrics_storage import (
    AggregatedRedisMetricsStorage,
    InMemoryMetricsStorage,
)


class _FailingRedisClient:
    def ping(self):
        raise ConnectionError("connection refused")


class _WorkingRedisClient:
    def ping(self):
        return True


def test_fallback_para_memoria_sem_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)

    storage = _create_storage()

    assert isinstance(storage, InMemoryMetricsStorage)


def test_usa_redis_quando_configurado_e_alcancavel(monkeypatch):
    """AggregatedRedisMetricsStorage (O(1) counters, Sprint 246), not the
    plain list-based RedisMetricsStorage — the production wiring prefers it
    since /cdn/metrics/summary is the only Redis-backed consumer in this
    app and it never needs raw event history, only aggregates."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *a, **k: _WorkingRedisClient())

    storage = _create_storage()

    assert isinstance(storage, AggregatedRedisMetricsStorage)


def test_fallback_para_memoria_quando_redis_configurado_mas_inalcancavel(monkeypatch):
    """This is the actual scenario the spec's "falha total se Redis cair"
    claim is about — REDIS_URL is set, but the connection/ping fails."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *a, **k: _FailingRedisClient())

    storage = _create_storage()

    assert isinstance(storage, InMemoryMetricsStorage)


def test_fallback_por_falha_de_redis_registra_warning_no_log(monkeypatch, caplog):
    """The fallback must be loud, not silent — an operator who believes
    metrics are persisted to Redis needs to see this, not discover it by
    noticing data missing after a restart."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1")
    monkeypatch.setattr(redis.Redis, "from_url", lambda *a, **k: _FailingRedisClient())

    with caplog.at_level("WARNING", logger="app.api.metrics"):
        _create_storage()

    assert "Redis" in caplog.text


def test_ausencia_de_redis_url_nao_gera_warning(monkeypatch, caplog):
    """Not having REDIS_URL configured at all is the normal dev/test
    posture, not a failure — it shouldn't be logged as one."""
    monkeypatch.delenv("REDIS_URL", raising=False)

    with caplog.at_level("WARNING", logger="app.api.metrics"):
        _create_storage()

    assert caplog.text == ""
