class AlertRateLimiter:
    """Fixed-window (not sliding-window — acceptable approximation, per
    this sprint's own scope) rate limit on how many alerts a single
    domain can trigger delivery attempts for within `window` seconds.

    `INCR` then `EXPIRE` only on the first increment (`current == 1`), not
    `GET` + `SET` — a `GET`-then-`SET` pattern has a real race (two
    concurrent requests could both read the same pre-increment value and
    both decide they're under the limit), the same class of bug already
    fixed for `should_emit_alert()` (Sprint 251) and `allow_alert()`
    (Sprint 259). `INCR` is atomic on its own; gating the `EXPIRE` call
    behind `current == 1` avoids resetting the window's remaining TTL on
    every single alert the way `AlertDigestManager.add()`'s `expire()`
    deliberately does — here the window must stay fixed once started, or
    a domain alerting continuously would never actually get rate-limited.
    """

    def __init__(self, client):
        self._client = client

    def _key(self, domain: str) -> str:
        return f"alert:rate:{domain}"

    def allow(self, domain: str, limit: int = 5, window: int = 300) -> bool:
        key = self._key(domain)
        current = self._client.incr(key)

        if current == 1:
            self._client.expire(key, window)

        return current <= limit
