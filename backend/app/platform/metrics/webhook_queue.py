import json


class WebhookQueue:
    """Redis-backed, persisted queue of pending webhook deliveries — unlike
    the direct `WebhookClient.send()` path (Sprint 252, still used as a
    fallback when no queue is configured), an item that fails to deliver
    here survives a process restart and is retried instead of being lost
    the moment the request that enqueued it finishes.

    A plain FIFO via `rpush`/`lpop` (`enqueue`/`requeue` push to the tail,
    `dequeue_batch` pops from the head) — the same simple list-based
    approach already used by `RedisMetricsStorage`, not a distributed
    queue (Kafka/SQS) or a Celery task: this project does have a Celery
    worker (`app/workers/celery_app.py`), but nothing in `app/platform/
    metrics/` uses it — this module is deliberately Redis-native and
    FastAPI-`BackgroundTasks`-driven throughout (Sprint 252's incident/
    webhook design), and introducing a second, unrelated async-task
    mechanism just for this one queue would be a bigger, unrequested
    architectural change than this sprint asked for.

    The webhook *target URL* is also queue-state (`get_url`/`set_url`),
    not a constructor argument: `POST /metrics/webhook` (Sprint 256) lets
    an admin change it at runtime, and `WebhookWorker` reads it fresh on
    every `process()` call, so that endpoint actually takes effect for
    already-enqueued items instead of being disconnected from delivery.
    """

    _QUEUE_KEY = "webhook:queue"
    _FAILED_KEY = "webhook:failed"
    _URL_KEY = "webhook:url"
    # Sprint 257 observability counters. "sent" counts every delivery
    # *attempt* (success or failure) — not just successful ones, despite
    # the spec's own literal "on successful delivery -> increment success
    # + sent" wording. Read literally, `sent` would only ever be touched
    # alongside `success`, making them always equal and `success_rate`
    # (`success / sent`) permanently 1.0 (or 0/0) regardless of how many
    # deliveries are actually failing/retrying — exactly the "not
    # transparent, not monitorable" outcome this sprint exists to fix.
    # `sent` is bumped by both `record_success()` and `record_retry()` so
    # the ratio is a genuine attempts-succeeded rate.
    _METRIC_SENT_KEY = "webhook:metrics:sent"
    _METRIC_SUCCESS_KEY = "webhook:metrics:success"
    _METRIC_FAILED_KEY = "webhook:metrics:failed"
    _METRIC_RETRY_KEY = "webhook:metrics:retry"
    _MAX_RETRIES = 3
    # Defensive caps, same reasoning as RedisMetricsStorage's max_len: a
    # producer that outpaces a failing/unconfigured consumer must not grow
    # these lists without bound.
    _MAX_QUEUE_SIZE = 10_000
    _MAX_FAILED_SIZE = 1_000

    def __init__(self, client):
        self._client = client

    def enqueue(self, payload: dict, url: str | None = None) -> None:
        """`url` (Sprint 258) is per-item and optional — when given,
        `WebhookWorker` delivers this specific item there instead of the
        queue's own shared `get_url()`/`set_url()` target, which lets
        multiple destinations (e.g. per-tenant alert channels) share one
        underlying queue/retry/dead-letter mechanism without needing a
        separate queue per destination. Omitted, item shape is identical
        to before Sprint 258 — full backward compatibility.
        """
        item = {"payload": payload, "retries": 0}
        if url:
            item["url"] = url

        self._client.rpush(self._QUEUE_KEY, json.dumps(item))
        self._client.ltrim(self._QUEUE_KEY, -self._MAX_QUEUE_SIZE, -1)

    def put_back(self, item: dict) -> None:
        """Returns `item` to the tail of the queue exactly as-is — unlike
        `requeue()`, this never increments its retry count or risks
        dead-lettering it. Used by `WebhookWorker` when an item can't even
        be attempted yet (no resolvable target URL): that's a
        configuration gap, not a delivery failure, so it shouldn't cost
        the item any of its retry budget (same reasoning Sprint 256
        originally applied to the whole queue when no URL was configured
        at all, now applied per-item).
        """
        self._client.rpush(self._QUEUE_KEY, json.dumps(item))

    def dequeue_batch(self, limit: int = 10) -> list[dict]:
        items = []

        for _ in range(limit):
            raw = self._client.lpop(self._QUEUE_KEY)
            if raw is None:
                break
            items.append(json.loads(raw))

        return items

    def requeue(self, item: dict) -> None:
        """Re-queues a delivery that just failed, incrementing its retry
        count first — once that count reaches `_MAX_RETRIES` (3 failed
        attempts total), the item moves to a bounded dead-letter list
        instead of going back to the work queue. Never silently dropped:
        the spec's own stated goal for this sprint ("failures aren't
        recorded -> invisible") would otherwise be defeated by the retry
        limit itself.
        """
        item = {**item, "retries": item.get("retries", 0) + 1}

        if item["retries"] >= self._MAX_RETRIES:
            self._client.rpush(self._FAILED_KEY, json.dumps(item))
            self._client.ltrim(self._FAILED_KEY, -self._MAX_FAILED_SIZE, -1)
            # The dead-letter transition itself, not every requeue — this
            # is what `metrics()`'s "failed" counts: items that exhausted
            # every retry, not every individual retry along the way (that's
            # "retry", recorded by the caller via record_retry() before
            # requeue() is even called).
            self._client.incr(self._METRIC_FAILED_KEY)
            return

        self._client.rpush(self._QUEUE_KEY, json.dumps(item))

    def queue_size(self) -> int:
        return self._client.llen(self._QUEUE_KEY)

    def failed_count(self) -> int:
        return self._client.llen(self._FAILED_KEY)

    def get_url(self) -> str | None:
        return self._client.get(self._URL_KEY)

    def set_url(self, url: str) -> None:
        self._client.set(self._URL_KEY, url)

    def record_success(self) -> None:
        """Called by `WebhookWorker` only after a delivery attempt actually
        succeeds — never speculatively, and never for an attempt that's
        about to be retried."""
        self._client.incr(self._METRIC_SENT_KEY)
        self._client.incr(self._METRIC_SUCCESS_KEY)

    def record_retry(self) -> None:
        """Called by `WebhookWorker` for a failed delivery attempt, before
        `requeue()` — every failed attempt counts here, whether it ends up
        actually requeued or immediately dead-lettered by that `requeue()`
        call (which separately bumps `failed` only in the dead-letter
        case)."""
        self._client.incr(self._METRIC_SENT_KEY)
        self._client.incr(self._METRIC_RETRY_KEY)

    def metrics(self) -> dict:
        sent = int(self._client.get(self._METRIC_SENT_KEY) or 0)
        success = int(self._client.get(self._METRIC_SUCCESS_KEY) or 0)
        failed = int(self._client.get(self._METRIC_FAILED_KEY) or 0)
        retry = int(self._client.get(self._METRIC_RETRY_KEY) or 0)

        return {
            "sent": sent,
            "success": success,
            "failed": failed,
            "retry": retry,
            "success_rate": (success / sent) if sent else 0.0,
        }
