"""Tests for WebhookQueue (Sprint 256: persisted, retried webhook
delivery — see webhook_queue.py's own docstring for why this is a plain
Redis list, not the project's existing but unrelated Celery worker)."""

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


def test_enqueue_dequeue_ordem_fifo():
    queue = WebhookQueue(_FakeRedisClient())

    queue.enqueue({"domain": "a.com"})
    queue.enqueue({"domain": "b.com"})

    items = queue.dequeue_batch(limit=10)

    assert [item["payload"]["domain"] for item in items] == ["a.com", "b.com"]
    assert all(item["retries"] == 0 for item in items)


def test_dequeue_batch_respeita_limit():
    queue = WebhookQueue(_FakeRedisClient())
    for i in range(5):
        queue.enqueue({"i": i})

    first_batch = queue.dequeue_batch(limit=2)

    assert len(first_batch) == 2
    assert queue.queue_size() == 3


def test_dequeue_batch_vazio_quando_fila_vazia():
    queue = WebhookQueue(_FakeRedisClient())

    assert queue.dequeue_batch(limit=10) == []


def test_requeue_incrementa_retries_e_volta_para_o_fim_da_fila():
    queue = WebhookQueue(_FakeRedisClient())
    queue.enqueue({"domain": "a.com"})
    item = queue.dequeue_batch(1)[0]

    queue.requeue(item)

    assert queue.queue_size() == 1
    requeued = queue.dequeue_batch(1)[0]
    assert requeued["retries"] == 1
    assert requeued["payload"]["domain"] == "a.com"


def test_requeue_apos_max_retries_vai_para_dead_letter_nao_e_perdido():
    """The bug this guards against: the original spec's worker silently
    dropped an item once its retry count was exhausted, with no record —
    directly contradicting this sprint's own stated goal ("failures
    aren't recorded -> invisible"). Confirms the item survives in a
    dead-letter list instead."""
    queue = WebhookQueue(_FakeRedisClient())
    queue.enqueue({"domain": "a.com"})
    item = queue.dequeue_batch(1)[0]

    queue.requeue(item)  # retries: 0 -> 1, still requeued
    item = queue.dequeue_batch(1)[0]
    assert item["retries"] == 1

    queue.requeue(item)  # retries: 1 -> 2, still requeued
    item = queue.dequeue_batch(1)[0]
    assert item["retries"] == 2

    queue.requeue(item)  # retries: 2 -> 3, dead-lettered instead

    assert queue.queue_size() == 0
    assert queue.failed_count() == 1


def test_get_url_none_antes_de_configurado():
    queue = WebhookQueue(_FakeRedisClient())

    assert queue.get_url() is None


def test_set_url_e_get_url_roundtrip():
    queue = WebhookQueue(_FakeRedisClient())

    queue.set_url("https://hooks.slack.com/services/abc")

    assert queue.get_url() == "https://hooks.slack.com/services/abc"


def test_queue_size_e_failed_count_zero_por_padrao():
    queue = WebhookQueue(_FakeRedisClient())

    assert queue.queue_size() == 0
    assert queue.failed_count() == 0
