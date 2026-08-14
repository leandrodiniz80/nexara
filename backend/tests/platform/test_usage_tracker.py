"""Tests for UsageTracker (Sprint 270)."""

from app.platform.usage.usage_tracker import UsageTracker


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, int] = {}

    def incrby(self, key, amount):
        self._values[key] = self._values.get(key, 0) + amount
        return self._values[key]

    def get(self, key):
        value = self._values.get(key)
        return str(value) if value is not None else None

    def delete(self, key):
        self._values.pop(key, None)


def test_get_zero_por_padrao():
    tracker = UsageTracker(_FakeRedisClient())

    assert tracker.get("tenant-a", "alerts_sent") == 0


def test_increment_incrementa_em_um_por_padrao():
    tracker = UsageTracker(_FakeRedisClient())

    tracker.increment("tenant-a", "alerts_sent")

    assert tracker.get("tenant-a", "alerts_sent") == 1


def test_increment_aceita_amount_customizado():
    tracker = UsageTracker(_FakeRedisClient())

    tracker.increment("tenant-a", "alerts_sent", amount=5)

    assert tracker.get("tenant-a", "alerts_sent") == 5


def test_increment_e_cumulativo():
    tracker = UsageTracker(_FakeRedisClient())

    tracker.increment("tenant-a", "alerts_sent")
    tracker.increment("tenant-a", "alerts_sent")
    tracker.increment("tenant-a", "alerts_sent")

    assert tracker.get("tenant-a", "alerts_sent") == 3


def test_metricas_diferentes_sao_independentes():
    tracker = UsageTracker(_FakeRedisClient())

    tracker.increment("tenant-a", "alerts_sent")
    tracker.increment("tenant-a", "domains_registered")

    assert tracker.get("tenant-a", "alerts_sent") == 1
    assert tracker.get("tenant-a", "domains_registered") == 1


def test_tenants_diferentes_sao_isolados():
    tracker = UsageTracker(_FakeRedisClient())

    tracker.increment("tenant-a", "alerts_sent")
    tracker.increment("tenant-b", "alerts_sent", amount=10)

    assert tracker.get("tenant-a", "alerts_sent") == 1
    assert tracker.get("tenant-b", "alerts_sent") == 10


def test_reset_zera_o_contador():
    tracker = UsageTracker(_FakeRedisClient())
    tracker.increment("tenant-a", "alerts_sent", amount=5)

    tracker.reset("tenant-a", "alerts_sent")

    assert tracker.get("tenant-a", "alerts_sent") == 0


def test_reset_nao_afeta_outras_metricas_ou_tenants():
    tracker = UsageTracker(_FakeRedisClient())
    tracker.increment("tenant-a", "alerts_sent", amount=5)
    tracker.increment("tenant-a", "domains_registered", amount=2)
    tracker.increment("tenant-b", "alerts_sent", amount=3)

    tracker.reset("tenant-a", "alerts_sent")

    assert tracker.get("tenant-a", "alerts_sent") == 0
    assert tracker.get("tenant-a", "domains_registered") == 2
    assert tracker.get("tenant-b", "alerts_sent") == 3
