class UsageTracker:
    """Generic, per-tenant, per-metric cumulative counter (Sprint 270) —
    deliberately has no notion of a reset period itself (unlike
    `PlatformAuth`'s own `requests_per_day` tracking, which auto-resets
    daily via `_usage_record()`): this is a billing/analytics primitive
    ("how much has this tenant used, in total, since we started
    counting"), not a rate limiter. Whether/how a given metric should
    reset (never, daily, on the customer's own monthly billing cycle) is
    a decision for whoever *enforces* a limit against it, not for this
    class — see `reset()` below, which exists so a caller can implement
    that policy explicitly, on whatever schedule makes sense for that
    specific metric.
    """

    def __init__(self, client):
        self._client = client

    def _key(self, tenant_id: str, metric: str) -> str:
        return f"usage:{tenant_id}:{metric}"

    def increment(self, tenant_id: str, metric: str, amount: int = 1) -> None:
        self._client.incrby(self._key(tenant_id, metric), amount)

    def get(self, tenant_id: str, metric: str) -> int:
        value = self._client.get(self._key(tenant_id, metric))
        return int(value or 0)

    def reset(self, tenant_id: str, metric: str) -> None:
        self._client.delete(self._key(tenant_id, metric))
