import json


class AlertDigestManager:
    """Per-tenant batch of alerts held back by `AlertRateLimiter` (Sprint
    260) instead of being dropped outright — a domain generating alerts
    faster than its rate limit allows still gets those alerts *seen*
    eventually, just grouped into one digest an admin can flush on demand
    (`POST /metrics/alerts/digest/flush`) rather than delivered one
    webhook at a time.

    `expire(key, 300)` on every `add()`, not just the first — same
    "reset on every write, so it only fires after genuine inactivity"
    reasoning already used by `RedisMetricsStorage`: a persistently noisy
    domain keeps its digest alive for as long as it keeps adding to it,
    while a digest nobody ever flushes and that goes quiet still cleans
    itself up instead of sitting in Redis forever.

    `flush()` reads then deletes as two separate calls, not one atomic
    operation — an `add()` racing exactly between them could in principle
    be swept up by the `delete()` without ever being returned. Accepted
    here the same way `WebhookQueue.dequeue_batch()` isn't a fully
    transactional read either: this is a best-effort digest, not a
    exactly-once queue, and the underlying incident is still tracked
    independently via `IncidentManager` regardless of what a digest flush
    happens to catch.
    """

    def __init__(self, client):
        self._client = client

    def _key(self, tenant_id: str) -> str:
        return f"alert:digest:{tenant_id}"

    def add(self, tenant_id: str, alert: dict) -> None:
        key = self._key(tenant_id)
        self._client.rpush(key, json.dumps(alert))
        self._client.expire(key, 300)

    def flush(self, tenant_id: str) -> list[dict]:
        key = self._key(tenant_id)
        items = self._client.lrange(key, 0, -1)
        self._client.delete(key)

        return [json.loads(item) for item in items]

    def size(self, tenant_id: str) -> int:
        return self._client.llen(self._key(tenant_id))
