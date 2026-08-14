"""Tests for WebhookQueue's delivery-observability counters (Sprint 257).

Real issue in the spec, fixed here — see webhook_queue.py's own docstring
for the full reasoning: taken literally, "on successful delivery ->
increment success + sent" means `sent` is only ever touched alongside
`success`, so the two counters would always be equal and `success_rate`
(`success / sent`) would always read 1.0 (or 0/0) no matter how many
deliveries are actually failing — the opposite of "monitorable". `sent`
here counts every delivery *attempt* (success or failure), so
`success_rate` is a genuine ratio.
"""

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


def test_metrics_zerado_em_fila_vazia():
    queue = WebhookQueue(_FakeRedisClient())

    assert queue.metrics() == {
        "sent": 0,
        "success": 0,
        "failed": 0,
        "retry": 0,
        "success_rate": 0.0,
    }


def test_record_success_incrementa_sent_e_success():
    queue = WebhookQueue(_FakeRedisClient())

    queue.record_success()
    queue.record_success()

    metrics = queue.metrics()
    assert metrics["sent"] == 2
    assert metrics["success"] == 2
    assert metrics["success_rate"] == 1.0


def test_record_retry_incrementa_sent_e_retry_nao_success():
    queue = WebhookQueue(_FakeRedisClient())

    queue.record_retry()

    metrics = queue.metrics()
    assert metrics["sent"] == 1
    assert metrics["retry"] == 1
    assert metrics["success"] == 0
    assert metrics["success_rate"] == 0.0


def test_requeue_ate_dead_letter_incrementa_failed():
    queue = WebhookQueue(_FakeRedisClient())
    queue.enqueue({"domain": "a.com"})
    item = queue.dequeue_batch(1)[0]

    queue.requeue(item)  # retries: 0 -> 1, still requeued, not dead-lettered
    item = queue.dequeue_batch(1)[0]
    queue.requeue(item)  # retries: 1 -> 2, still requeued
    item = queue.dequeue_batch(1)[0]
    queue.requeue(item)  # retries: 2 -> 3, dead-lettered

    assert queue.metrics()["failed"] == 1


def test_requeue_que_nao_esgota_retries_nao_incrementa_failed():
    queue = WebhookQueue(_FakeRedisClient())
    queue.enqueue({"domain": "a.com"})
    item = queue.dequeue_batch(1)[0]

    queue.requeue(item)  # retries: 0 -> 1, still requeued

    assert queue.metrics()["failed"] == 0


def test_success_rate_calculo_com_sucessos_e_retries_misturados():
    """The scenario the literal spec wording couldn't represent: some
    attempts succeed, some fail and get retried — success_rate must
    reflect that mix, not always read 1.0."""
    queue = WebhookQueue(_FakeRedisClient())

    queue.record_success()
    queue.record_success()
    queue.record_retry()

    metrics = queue.metrics()
    assert metrics["sent"] == 3
    assert metrics["success"] == 2
    assert metrics["retry"] == 1
    assert metrics["success_rate"] == 2 / 3


def test_metrics_e_independente_do_estado_da_fila_em_si():
    """Counters survive past items being dequeued/delivered — they track
    cumulative delivery history, not current queue occupancy."""
    queue = WebhookQueue(_FakeRedisClient())
    queue.record_success()

    queue.enqueue({"domain": "a.com"})
    queue.dequeue_batch(1)

    assert queue.metrics()["success"] == 1
