"""Tests for WebhookWorker (Sprint 256) — drains a WebhookQueue, retrying
failed deliveries up to WebhookQueue's own limit (3) via requeue(), and
never silently dropping an item once that limit is hit (see
test_webhook_queue.py for the dead-letter guarantee itself)."""

from app.platform.metrics.webhook_queue import WebhookQueue
from app.platform.metrics.webhook_worker import WebhookWorker


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


class _AlwaysSucceedsClient:
    def __init__(self, url, timeout_seconds=2.0):
        self.url = url

    def send(self, payload: dict) -> bool:
        return True


class _AlwaysFailsClient:
    def __init__(self, url, timeout_seconds=2.0):
        self.url = url

    def send(self, payload: dict) -> bool:
        return False


def test_process_sem_url_configurada_nao_mexe_na_fila():
    """No configured target yet is a config gap, not a delivery failure —
    items must stay queued untouched (not dequeued/requeued, which would
    needlessly burn their retry budget) until a URL is set."""
    queue = WebhookQueue(_FakeRedisClient())
    queue.enqueue({"domain": "a.com"})
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)

    result = worker.process()

    assert result == {"sent": 0, "failed": 0, "processed": 0}
    assert queue.queue_size() == 1


def test_process_entrega_com_sucesso_remove_da_fila():
    queue = WebhookQueue(_FakeRedisClient())
    queue.set_url("https://hooks.example.com/webhook")
    queue.enqueue({"domain": "a.com"})
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)

    result = worker.process()

    assert result == {"sent": 1, "failed": 0, "processed": 1}
    assert queue.queue_size() == 0


def test_process_falha_requeue_o_item_para_nova_tentativa():
    queue = WebhookQueue(_FakeRedisClient())
    queue.set_url("https://hooks.example.com/webhook")
    queue.enqueue({"domain": "a.com"})
    worker = WebhookWorker(queue, client_factory=_AlwaysFailsClient)

    result = worker.process()

    assert result == {"sent": 0, "failed": 1, "processed": 1}
    assert queue.queue_size() == 1


def test_process_apos_falhas_repetidas_item_vai_para_dead_letter_nao_e_perdido():
    """The bug fixed relative to the original spec: retry exhaustion must
    be visible (dead-lettered), never a silent drop."""
    queue = WebhookQueue(_FakeRedisClient())
    queue.set_url("https://hooks.example.com/webhook")
    queue.enqueue({"domain": "a.com"})
    worker = WebhookWorker(queue, client_factory=_AlwaysFailsClient)

    worker.process()  # retries: 0 -> 1
    worker.process()  # retries: 1 -> 2
    worker.process()  # retries: 2 -> 3, dead-lettered

    assert queue.queue_size() == 0
    assert queue.failed_count() == 1


def test_process_respeita_limit():
    queue = WebhookQueue(_FakeRedisClient())
    queue.set_url("https://hooks.example.com/webhook")
    for i in range(5):
        queue.enqueue({"i": i})
    worker = WebhookWorker(queue, client_factory=_AlwaysSucceedsClient)

    result = worker.process(limit=2)

    assert result["processed"] == 2
    assert queue.queue_size() == 3


def test_process_usa_url_atual_da_fila_nao_uma_fixada_na_construcao():
    """WebhookWorker must read the target URL fresh from the queue on
    every call, not lock onto whatever URL existed when it was
    constructed — otherwise POST /metrics/webhook (which calls
    queue.set_url()) would have no actual effect on delivery."""
    seen_urls = []

    class _RecordingClient:
        def __init__(self, url, timeout_seconds=2.0):
            seen_urls.append(url)

        def send(self, payload):
            return True

    queue = WebhookQueue(_FakeRedisClient())
    worker = WebhookWorker(queue, client_factory=_RecordingClient)

    queue.set_url("https://first.example.com")
    queue.enqueue({"domain": "a.com"})
    worker.process()

    queue.set_url("https://second.example.com")
    queue.enqueue({"domain": "b.com"})
    worker.process()

    assert seen_urls == ["https://first.example.com", "https://second.example.com"]
