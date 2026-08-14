class ApiRateLimiter:
    """Fixed-window rate limit on API-key-authenticated requests (Sprint
    267) — same shape as `AlertRateLimiter` (Sprint 260): atomic `INCR`,
    `EXPIRE` only on the window's first increment (not every call, or the
    window would keep sliding forward and a continuously-calling
    integration would never actually get limited).

    Callers must pass an already-hashed key (`hash_api_key()` from
    `api_key_manager.py`), never the raw value — the spec's own version
    used the raw key directly as part of the Redis key name
    (`f"rate:apikey:{key}"`), which would have put the secret at rest in
    Redis (as a scannable key name, not a value) right next to the whole
    reason Sprint 267 exists: never persisting the raw key anywhere.
    """

    def __init__(self, client):
        self._client = client

    def _key(self, key_hash: str) -> str:
        return f"rate:apikey:{key_hash}"

    def allow(self, key_hash: str, limit: int = 100, window: int = 60) -> bool:
        redis_key = self._key(key_hash)
        current = self._client.incr(redis_key)

        if current == 1:
            self._client.expire(redis_key, window)

        return current <= limit
