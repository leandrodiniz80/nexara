"""Dependency wiring for `ApiKeyManager`/`ApiRateLimiter` (Sprint 266,
extended in 267) — deliberately its own module and lazy singletons,
mirroring `app/api/dependencies/metrics.py`'s established
`_create_storage()`/`get_metrics_store()` pattern, rather than the
spec's own `container.api_keys()` / `getattr(container,
"api_rate_limiter", None)`.

`PlatformContainer` has no Redis awareness at all (only the generic
`PlatformStorage`/`PlatformCache` abstractions `PlatformAuth` uses for
its own blob-persistence, which don't support the set/hash operations
`ApiKeyManager` needs) — the only place a real `redis.Redis` client gets
constructed anywhere in this codebase is `get_metrics_store()`'s own lazy
`_create_storage()`. Rather than either wedging Redis-client construction
into the frozen, non-Redis-aware `PlatformContainer` model, or reaching
into the metrics store's already-constructed storage for an unrelated,
non-metrics concern, this reuses that same proven "lazy Redis client,
module-level singleton, plain dependency function" shape independently
— one shared client, matching `_create_storage()`'s own "one client, many
managers" wiring, not a second connection per manager.
"""

import logging
import os

from fastapi import Depends, Header, HTTPException

from app.platform.tenant.api_key_manager import ApiKeyManager, hash_api_key
from app.platform.tenant.api_rate_limiter import ApiRateLimiter

logger = logging.getLogger("app.api.api_keys")

_api_key_client = None
_api_key_manager: ApiKeyManager | None = None
_api_rate_limiter: ApiRateLimiter | None = None
_CONNECT_TIMEOUT_SECONDS = 2


class _InMemoryKeyValueClient:
    """Fallback when `REDIS_URL` isn't set/reachable — same role as
    `InMemoryMetricsStorage` plays for the metrics subsystem: keeps the
    feature usable (single-process dev/test) without Redis, at the same
    already-accepted cost (no persistence across a restart, no sharing
    across multiple worker processes in a real multi-worker deployment).
    """

    def __init__(self):
        self._strings: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._hashes: dict[str, dict] = {}

    def get(self, key):
        return self._strings.get(key)

    def set(self, key, value):
        self._strings[key] = value

    def delete(self, key):
        self._strings.pop(key, None)
        self._hashes.pop(key, None)

    def sadd(self, key, value):
        self._sets.setdefault(key, set()).add(value)

    def srem(self, key, value):
        self._sets.get(key, set()).discard(value)

    def smembers(self, key):
        return set(self._sets.get(key, set()))

    def hset(self, key, mapping):
        self._hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key):
        return dict(self._hashes.get(key, {}))

    def incr(self, key):
        self._strings[key] = str(int(self._strings.get(key, 0)) + 1)
        return int(self._strings[key])

    def expire(self, key, ttl):
        return True


def _create_api_key_client():
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        return _InMemoryKeyValueClient()

    try:
        import redis

        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_CONNECT_TIMEOUT_SECONDS,
        )
        client.ping()

        return client
    except Exception:
        logger.warning("REDIS_URL is set but Redis is unreachable; API keys stay in-memory")
        return _InMemoryKeyValueClient()


def _get_shared_client():
    global _api_key_client

    if _api_key_client is None:
        _api_key_client = _create_api_key_client()

    return _api_key_client


def get_api_key_manager() -> ApiKeyManager:
    global _api_key_manager

    if _api_key_manager is None:
        _api_key_manager = ApiKeyManager(_get_shared_client())

    return _api_key_manager


def get_api_rate_limiter() -> ApiRateLimiter:
    global _api_rate_limiter

    if _api_rate_limiter is None:
        _api_rate_limiter = ApiRateLimiter(_get_shared_client())

    return _api_rate_limiter


def get_optional_api_key_tenant(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    api_key_manager: ApiKeyManager = Depends(get_api_key_manager),
    api_rate_limiter: ApiRateLimiter = Depends(get_api_rate_limiter),
) -> str | None:
    """`None` when no `X-API-Key` header is present at all — lets a route
    fall back to session auth (Sprint 266's own explicit "don't remove
    session auth" requirement). 403, not silently `None`, when a header
    *was* sent but doesn't map to any tenant: a caller who deliberately
    tried API-key auth and got it wrong deserves a clear rejection, not a
    silent, confusing fallback to "you're not authenticated at all".

    The spec's own version (`get_api_key_tenant`) always raised 401 for a
    missing header — unusable as an optional, session-or-API-key
    dependency the way Part 5 of that same spec explicitly asks for; used
    directly, it would have made every route that adds it a *harder*
    requirement (API key mandatory) instead of an *additional* one.

    Rate limiting (Sprint 267): checked only for a key that's actually
    valid — an invalid key shouldn't consume (or be blocked by) a rate
    budget it was never entitled to in the first place. Rate-limited by
    `hash_api_key(x_api_key)`, not the raw key (the spec's own version,
    `f"rate:apikey:{key}"` with the raw value) — using the raw key as
    part of a Redis key name would put the secret at rest in Redis
    (visible via `SCAN`, potentially logged) right next to this whole
    sprint's own point: never persisting it anywhere, in any form.
    """
    if not x_api_key:
        return None

    tenant_id = api_key_manager.get_tenant(x_api_key)

    if not tenant_id:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    if not api_rate_limiter.allow(hash_api_key(x_api_key)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return tenant_id
