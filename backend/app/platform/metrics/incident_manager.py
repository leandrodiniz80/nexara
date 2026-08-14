import json
import time


class IncidentManager:
    """Redis-backed incident lifecycle tracking (open -> ongoing -> resolved
    -> history), layered on top of the anomaly detection in
    `LoaderMetricsStore.detect_anomalies()`. One active incident per
    (domain, type) composite key — never duplicated: `open_or_update()`
    always reads the existing active record first and updates it in place
    if one exists, only creating a new one when none does.

    History is written and read per-domain (`incident:history:{domain}`),
    deliberately never a single flat/global list: an unscoped history would
    leak every tenant's incidents to whichever caller reads it first — the
    same class of cross-tenant leak already fixed for `/metrics/dashboard`
    (Sprint 248) and `/metrics/summary` (Sprint 243). `/metrics/incidents`
    (cdn.py) only ever reads the domains the caller's own organization owns.

    Takes a duck-typed Redis client, same as `AggregatedRedisMetricsStorage`
    — does no connection management itself.
    """

    # The closed vocabulary LoaderMetricsStore._alert_type() can produce —
    # get_active() checks exactly these composite keys rather than
    # SCAN-ing the keyspace for "whatever types happen to exist": the
    # established convention in this codebase (Sprint 247's KEYS -> SCAN
    # fix) is to avoid keyspace scans, and here there's a small, known,
    # closed set of types to check directly instead of one at all.
    _KNOWN_TYPES = ("error", "latency", "unknown")

    def __init__(self, redis_client, ttl_seconds: int = 86400, history_limit: int = 1000):
        self._client = redis_client
        self._ttl = ttl_seconds
        self._history_limit = history_limit

    def _active_key(self, domain: str, alert_type: str) -> str:
        return f"incident:active:{domain}:{alert_type}"

    def _history_key(self, domain: str) -> str:
        return f"incident:history:{domain}"

    def open_or_update(self, domain: str, alert_type: str, data: dict) -> dict:
        """`data` supplies the fields to record — at minimum `severity`.
        `alert_type` comes from the caller (`LoaderMetricsStore._alert_type()`),
        not re-derived here: deciding "was this an error spike or a latency
        spike" from spike values alone, independently of the thresholds
        that actually classified the alert's severity, risks disagreeing
        with that classification and mislabeling the incident.
        """
        key = self._active_key(domain, alert_type)
        existing = self._client.get(key)
        now = int(time.time())

        if existing:
            incident = json.loads(existing)
            incident["last_seen"] = now
            incident["severity"] = data.get("severity", incident.get("severity"))
            incident["count"] = incident.get("count", 0) + 1
            self._client.set(key, json.dumps(incident), ex=self._ttl)

            return {"status": "ongoing", "incident": incident}

        incident = {
            "id": f"{domain}:{alert_type}:{now}",
            "domain": domain,
            "type": alert_type,
            "severity": data.get("severity"),
            "started_at": now,
            "last_seen": now,
            "count": 1,
        }
        self._client.set(key, json.dumps(incident), ex=self._ttl)

        return {"status": "open", "incident": incident}

    def resolve(self, domain: str, alert_type: str, data: dict | None = None) -> dict | None:
        """`data`, if given, is merged into the incident record before it's
        archived — e.g. the final observed error rate/latency at
        resolution time, for a richer history entry. Optional: callers
        opportunistically resolving a possibly-nonexistent incident (e.g.
        `detect_anomalies()` trying every known type once severity drops
        to "low") don't need anything to attach.
        """
        key = self._active_key(domain, alert_type)
        existing = self._client.get(key)

        if not existing:
            return None

        incident = json.loads(existing)
        if data:
            incident.update(data)

        now = int(time.time())
        incident["resolved_at"] = now
        incident["duration"] = now - incident["started_at"]

        history_key = self._history_key(domain)
        self._client.lpush(history_key, json.dumps(incident))
        self._client.ltrim(history_key, 0, self._history_limit - 1)
        self._client.expire(history_key, self._ttl)

        self._client.delete(key)

        return incident

    def get_active(self, domain: str) -> list[dict]:
        active = []

        for alert_type in self._KNOWN_TYPES:
            raw = self._client.get(self._active_key(domain, alert_type))
            if raw:
                active.append(json.loads(raw))

        return active

    def get_history(self, domain: str, limit: int = 100) -> list[dict]:
        raw = self._client.lrange(self._history_key(domain), 0, limit - 1)
        return [json.loads(item) for item in raw]
