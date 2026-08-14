"""Tests for ProcessedStripeEventStore (Sprint 269)."""

from app.platform.billing.processed_events_store import ProcessedStripeEventStore


class _FakeRedisClient:
    def __init__(self):
        self._values: dict[str, tuple] = {}

    def get(self, key):
        return self._values.get(key, (None,))[0]

    def set(self, key, value, ex=None):
        self._values[key] = (value, ex)
        return True


def test_has_processed_falso_por_padrao():
    store = ProcessedStripeEventStore(_FakeRedisClient())

    assert store.has_processed("evt_1") is False


def test_mark_processed_depois_has_processed_e_verdadeiro():
    store = ProcessedStripeEventStore(_FakeRedisClient())

    store.mark_processed("evt_1")

    assert store.has_processed("evt_1") is True


def test_eventos_diferentes_sao_independentes():
    store = ProcessedStripeEventStore(_FakeRedisClient())

    store.mark_processed("evt_1")

    assert store.has_processed("evt_2") is False


def test_mark_processed_seta_ttl():
    client = _FakeRedisClient()
    store = ProcessedStripeEventStore(client, ttl_seconds=3600)

    store.mark_processed("evt_1")

    _, ttl = client._values["stripe:event:evt_1"]
    assert ttl == 3600


def test_ttl_default_e_generoso_o_suficiente_para_retries_do_stripe():
    """Stripe's own documented retry window is up to ~72h; the default
    must comfortably exceed that."""
    client = _FakeRedisClient()
    store = ProcessedStripeEventStore(client)

    store.mark_processed("evt_1")

    _, ttl = client._values["stripe:event:evt_1"]
    assert ttl > 72 * 3600
