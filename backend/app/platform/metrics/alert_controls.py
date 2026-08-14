import time


class AlertControlManager:
    """Manual silencing + cooldown for alert delivery (Sprint 259) — an
    anti-spam layer that sits in front of `_send_webhook()`'s existing
    delivery mechanisms (single webhook, Sprint 256; per-tenant channels,
    Sprint 258), gating whether an alert gets *delivered* at all. Never
    touches incident tracking or the alert's own structure — a silenced/
    cooldown-blocked alert still opens/updates its incident and still
    shows up in `/metrics/alerts`/`/metrics/incidents`, only its outbound
    webhook is suppressed.
    """

    _SILENCE_PREFIX = "alert:silenced:"

    def __init__(self, client):
        self._client = client

    def _silence_key(self, domain: str) -> str:
        return f"{self._SILENCE_PREFIX}{domain}"

    def silence(self, domain: str, seconds: int) -> None:
        """Stores the silence's own expiry timestamp as the value (so
        `is_silenced()` works correctly independent of how precisely the
        backing store honors TTLs) *and* sets a real TTL on the key
        (`ex=seconds`) so a long-forgotten silence doesn't sit in Redis
        forever — the same "value carries the truth, TTL is cleanup, not
        the mechanism" approach already used by `AggregatedRedisMetrics
        Storage.should_emit_alert()`'s debounce key.
        """
        self._client.set(self._silence_key(domain), int(time.time()) + seconds, ex=seconds)

    def is_silenced(self, domain: str) -> bool:
        value = self._client.get(self._silence_key(domain))

        if not value:
            return False

        return int(value) > int(time.time())

    def unsilence(self, domain: str) -> None:
        self._client.delete(self._silence_key(domain))

    def list_silenced(self) -> list[str]:
        """`SCAN` (via `scan_iter`), not `KEYS` — the same anti-pattern fix
        already established for `AggregatedRedisMetricsStorage.
        top_domains()` (Sprint 247): `KEYS` blocks the whole Redis instance
        for every other client while it walks the entire keyspace.

        Re-checks `is_silenced()` per matched key rather than trusting
        every key `SCAN` finds to still be genuinely active: a real Redis
        TTL should have already removed an expired silence, but this
        stays correct even if a key briefly outlives its logical expiry
        (e.g. a backend that doesn't honor `ex` precisely), instead of
        listing a domain as silenced when it no longer is.
        """
        domains = []

        for key in self._client.scan_iter(match=f"{self._SILENCE_PREFIX}*"):
            domain = key[len(self._SILENCE_PREFIX) :]
            if self.is_silenced(domain):
                domains.append(domain)

        return domains

    def _cooldown_key(self, domain: str, alert_type: str) -> str:
        return f"alert:cooldown:{domain}:{alert_type}"

    def allow_alert(self, domain: str, alert_type: str, cooldown: int) -> bool:
        """`True` at most once per `cooldown` seconds for a given
        domain+type. A single atomic `SET ... NX EX`, not the spec's own
        separate `GET` then `SET` — the same race the codebase already
        fixed once for `should_emit_alert()` (Sprint 251): a crash, or
        just two concurrent requests, between a `GET` and a `SET` could
        let both pass the cooldown check and double-send. This method's
        desired behavior ("true only once per window, and mark it as
        fired for that duration") is exactly what `should_emit_alert()`
        already does, so it reuses the identical atomic pattern.
        """
        key = self._cooldown_key(domain, alert_type)

        return bool(self._client.set(key, int(time.time()), nx=True, ex=cooldown))
