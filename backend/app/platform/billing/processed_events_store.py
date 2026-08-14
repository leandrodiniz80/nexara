_DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # 30 days


class ProcessedStripeEventStore:
    """Persistent, shared idempotency tracking for Stripe webhook event
    ids (Sprint 269) — `StripeService`'s own in-memory `set()` (still the
    default when no store is injected) only tracks what *this one
    process* has seen; in a real multi-worker deployment, a redelivered
    event landing on a different worker than the one that handled it
    first would never be recognized as a duplicate. Stripe's own
    documented retry window is up to ~72 hours, so a 30-day TTL is a
    generous, bounded margin — not indefinite growth, but comfortably
    longer than any retry could still be relevant.
    """

    def __init__(self, client, ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        self._client = client
        self._ttl = ttl_seconds

    def _key(self, event_id: str) -> str:
        return f"stripe:event:{event_id}"

    def has_processed(self, event_id: str) -> bool:
        return self._client.get(self._key(event_id)) is not None

    def mark_processed(self, event_id: str) -> None:
        self._client.set(self._key(event_id), "1", ex=self._ttl)
