import json
import threading
from collections import deque
from datetime import datetime, timedelta, timezone


class MetricsStorage:
    """Plain class with no-op defaults, not an ABC — matching every other
    pluggable storage interface in this platform (`PlatformStorage`,
    `PlatformCache`, `BrandingStorage`, `LogoStorage`), none of which use
    `abc.ABC`.
    """

    def add(self, event: dict) -> None:
        pass

    def list(self) -> list[dict]:
        return []


class InMemoryMetricsStorage(MetricsStorage):
    def __init__(self, maxlen: int = 10_000):
        # Every loader page-load across every customer domain can produce an
        # event (Sprint 242's fire-and-forget beacon) — an unbounded deque
        # would grow without limit under real traffic. `maxlen` keeps this
        # viable as a stopgap until a real backend (Redis/Postgres) lands.
        self._lock = threading.Lock()
        self._events: deque = deque(maxlen=maxlen)

    def add(self, event: dict) -> None:
        with self._lock:
            self._events.append(event)

    def list(self) -> list[dict]:
        with self._lock:
            return list(self._events)


class RedisMetricsStorage(MetricsStorage):
    """Backed by any duck-typed client with `.rpush()`/`.lrange()`/
    `.ltrim()`/`.expire()` (e.g. `redis.Redis`) — this class does no
    connection management itself, `get_metrics_store()` owns that.

    Bounded two ways, not just one:
    - `LTRIM` after every write caps the list at `max_len` entries
      regardless of traffic volume — under continuous load, `EXPIRE` alone
      never fires (it keeps getting pushed back on every write), so it
      cannot bound memory on its own; only a size cap does that.
    - `EXPIRE` (reset on every write, so it only fires after `ttl_seconds`
      of genuine *inactivity*) is a second, independent safety net: if a
      domain stops sending events entirely, its data still eventually
      disappears instead of sitting forever.
    """

    def __init__(
        self,
        client,
        key: str = "loader_metrics",
        ttl_seconds: int = 86400,
        max_len: int = 10_000,
    ):
        self._client = client
        self._key = key
        self._ttl = ttl_seconds
        self._max_len = max_len

    def add(self, event: dict) -> None:
        self._client.rpush(self._key, json.dumps(event))
        self._client.ltrim(self._key, -self._max_len, -1)
        self._client.expire(self._key, self._ttl)

    def list(self) -> list[dict]:
        raw = self._client.lrange(self._key, 0, -1)
        return [json.loads(item) for item in raw]


class AggregatedRedisMetricsStorage(MetricsStorage):
    """O(1) counters per domain (plus a global scope for the unfiltered,
    all-domains query) instead of a scanned list — `summary()` never
    re-reads full event history the way `LoaderMetricsStore`'s scan-based
    fallback does over `RedisMetricsStorage`/`InMemoryMetricsStorage`. This
    is what keeps `/cdn/metrics/summary` fast under real, continuous
    traffic, where a growing list means an ever more expensive scan on
    every dashboard read.

    Deliberately does NOT support `list()`: keeping a parallel raw event
    log next to these counters would defeat the entire point of O(1)
    aggregation (that log would still need its own trimming/scanning).
    Anything that genuinely needs raw event history should use
    `RedisMetricsStorage` instead — `list()` here raises loudly rather than
    silently returning `[]`, which would look identical to "no events yet".
    """

    _GLOBAL_SCOPE = "__global__"
    # Enough hourly buckets for a full 7-day window (Sprint 249's stated
    # goal) plus a day of headroom, so a bucket never expires mid-read.
    _DEFAULT_BUCKET_TTL_SECONDS = 8 * 24 * 3600
    # Hard cap on how many hourly buckets a single summary_window() call
    # will read — an authenticated-but-not-staff caller can pass any
    # `hours` value (see cdn.py), and this endpoint has no per-request
    # Redis-cost limit otherwise; 30 days of hourly buckets is already far
    # more than the 1h/24h/7d views this sprint actually needs.
    _MAX_WINDOW_HOURS = 24 * 30

    def __init__(
        self,
        client,
        bucket_ttl_seconds: int = _DEFAULT_BUCKET_TTL_SECONDS,
        incident_manager=None,
        webhook=None,
        webhook_queue=None,
        webhook_worker=None,
        channel_manager=None,
        alert_controls=None,
        alert_digest=None,
        rate_limiter=None,
        usage_tracker=None,
    ):
        self._client = client
        self._bucket_ttl = bucket_ttl_seconds
        # Optional capabilities (Sprint 252, plus webhook_queue/
        # webhook_worker in Sprint 256, channel_manager in Sprint 258,
        # alert_controls in Sprint 259, alert_digest/rate_limiter in
        # Sprint 260), public and untyped here — same convention as
        # `client` itself,
        # which this class also never type-hints — so `LoaderMetricsStore`
        # can detect and use them via plain attribute access
        # (`getattr(storage, "incident_manager", None)`), the same pattern
        # already used for summary/top_domains/summary_window/
        # should_emit_alert. `None` means the capability simply isn't
        # configured, not an error. `channel_manager` lives here, not as
        # a `LoaderMetricsStore` constructor param (as the Sprint 258
        # spec's own wiring proposed) — that would break the same
        # "thin aggregation layer over a pluggable MetricsStorage"
        # separation `incident_manager`/`webhook`/`webhook_queue`/
        # `webhook_worker` already respect, and the spec's own proposed
        # `LoaderMetricsStore(storage=..., incident_manager=...,
        # webhook=..., channel_manager=...)` call doesn't match this
        # class's actual constructor at all (it only ever took `storage`).
        self.incident_manager = incident_manager
        self.webhook = webhook
        self.webhook_queue = webhook_queue
        self.webhook_worker = webhook_worker
        self.channel_manager = channel_manager
        self.alert_controls = alert_controls
        # Stored without a leading underscore, unlike the spec's own
        # `self._alert_digest`/`self._rate_limiter` — every other optional
        # capability on this class is a public attribute specifically so
        # `getattr(storage, "x", None)` from LoaderMetricsStore is a
        # legitimate use of this class's own declared interface, not a
        # private-attribute reach-through. A leading underscore here would
        # have made `LoaderMetricsStore`'s delegation methods do exactly
        # the kind of encapsulation-breaking access this whole capability
        # pattern exists to avoid (Sprints 251/253/256/258/259).
        self.alert_digest = alert_digest
        self.rate_limiter = rate_limiter
        # Sprint 270 — same public, no-underscore convention as every
        # other optional capability above.
        self.usage_tracker = usage_tracker

    def _key(self, scope: str, metric: str) -> str:
        return f"metrics:{scope}:{metric}"

    @staticmethod
    def _bucket_for(moment: datetime) -> str:
        return moment.strftime("%Y%m%d%H")

    def _bucket_key(self, domain: str, bucket: str, metric: str) -> str:
        return f"metrics:{domain}:bucket:{bucket}:{metric}"

    def add(self, event: dict) -> None:
        domain = event.get("domain")
        is_success = event.get("event") == "success"
        is_error = event.get("event") == "error"
        duration = event.get("duration")

        scopes = [self._GLOBAL_SCOPE]
        if domain:
            scopes.append(domain)

        pipe = self._client.pipeline()

        for scope in scopes:
            pipe.incr(self._key(scope, "total"))

            if is_success:
                pipe.incr(self._key(scope, "success"))

                # Matches the scan-based summary's existing semantics:
                # avg_duration is the mean duration of *successful* events
                # only, not of every event that happens to report one.
                if duration is not None:
                    pipe.incrbyfloat(self._key(scope, "success_duration_sum"), duration)
                    pipe.incr(self._key(scope, "success_duration_count"))

            if is_error:
                pipe.incr(self._key(scope, "errors"))

        # Time-bucketed counters (Sprint 249) — domain-scoped only, not
        # global: nothing currently reads a platform-wide windowed summary,
        # so writing (and later expiring) a global bucket every event would
        # just be cost with no reader. Same pipeline as the writes above —
        # one round trip, not two.
        if domain:
            bucket = self._bucket_for(datetime.now(timezone.utc))
            bucket_metrics = ["total"]

            pipe.incr(self._bucket_key(domain, bucket, "total"))

            if is_success:
                pipe.incr(self._bucket_key(domain, bucket, "success"))
                bucket_metrics.append("success")

                if duration is not None:
                    pipe.incrbyfloat(
                        self._bucket_key(domain, bucket, "success_duration_sum"), duration
                    )
                    pipe.incr(self._bucket_key(domain, bucket, "success_duration_count"))
                    bucket_metrics += ["success_duration_sum", "success_duration_count"]

            if is_error:
                pipe.incr(self._bucket_key(domain, bucket, "error"))
                bucket_metrics.append("error")

            for metric in bucket_metrics:
                pipe.expire(self._bucket_key(domain, bucket, metric), self._bucket_ttl)

        pipe.execute()

    def _read_scope(self, scope: str, domain: str | None) -> dict:
        total = int(self._client.get(self._key(scope, "total")) or 0)
        success = int(self._client.get(self._key(scope, "success")) or 0)
        errors = int(self._client.get(self._key(scope, "errors")) or 0)
        duration_sum = float(self._client.get(self._key(scope, "success_duration_sum")) or 0)
        duration_count = int(self._client.get(self._key(scope, "success_duration_count")) or 0)

        return {
            "domain": domain,
            "total": total,
            "success": success,
            "error": errors,
            "avg_duration": (duration_sum / duration_count) if duration_count else None,
            "error_rate": (errors / total) if total else None,
        }

    def summary(self, domain: str | None = None) -> dict:
        scope = domain if domain else self._GLOBAL_SCOPE

        return self._read_scope(scope, domain)

    _WINDOW_METRICS = (
        "total",
        "success",
        "error",
        "success_duration_sum",
        "success_duration_count",
    )

    def summary_window(self, domain: str, hours: int, offset: int = 0) -> dict:
        """Same shape as `summary()`, scoped to the `hours`-hour window
        starting `offset` hours ago — `offset=0` (default) is "the last
        `hours` hours up to and including the current one"; `offset=1`
        means "the `hours` hours before the current one, excluding it".
        `detect_anomalies()` (Sprint 251) relies on that second form for
        its baseline: comparing the last 1h against a 24h window that
        *includes* that same hour dilutes a spike into its own baseline
        instead of measuring it against clean prior data.

        Reads are pipelined (one round trip for every bucket/metric
        combination, not one round trip per `.get()` call): a naive
        sequential loop here would mean up to `hours * len(_WINDOW_METRICS)`
        individual Redis calls for a *single* domain — for a 7-day window
        across even a handful of domains, `domains_summary_window()` would
        turn one dashboard request into thousands of sequential round trips.
        """
        hours = max(1, min(hours, self._MAX_WINDOW_HOURS))
        offset = max(0, offset)
        now = datetime.now(timezone.utc)
        buckets = [self._bucket_for(now - timedelta(hours=offset + i)) for i in range(hours)]

        pipe = self._client.pipeline()
        for bucket in buckets:
            for metric in self._WINDOW_METRICS:
                pipe.get(self._bucket_key(domain, bucket, metric))
        raw_values = pipe.execute()

        total = success = errors = 0
        duration_sum = 0.0
        duration_count = 0
        width = len(self._WINDOW_METRICS)

        for i in range(len(buckets)):
            bucket_total, bucket_success, bucket_error, bsum, bcount = raw_values[
                i * width : (i + 1) * width
            ]
            total += int(bucket_total or 0)
            success += int(bucket_success or 0)
            errors += int(bucket_error or 0)
            duration_sum += float(bsum or 0)
            duration_count += int(bcount or 0)

        return {
            "domain": domain,
            "total": total,
            "success": success,
            "error": errors,
            "avg_duration": (duration_sum / duration_count) if duration_count else None,
            "error_rate": (errors / total) if total else None,
        }

    def should_emit_alert(self, key: str, window_seconds: int = 300) -> bool:
        """Redis-backed debounce: `True` at most once per `window_seconds`
        for a given `key`. Uses a single atomic `SET ... NX EX`, not a
        separate `SETNX` followed by `EXPIRE`: a crash between those two
        calls would leave the debounce key set with no TTL at all,
        permanently suppressing every future alert for that key until
        someone notices and deletes it by hand. Fails open (`True`) if
        Redis errors out — a transient outage should degrade to "no
        debounce protection right now", not silently swallow a real alert.
        """
        debounce_key = f"alerts:debounce:{key}"

        try:
            return bool(self._client.set(debounce_key, "1", nx=True, ex=window_seconds))
        except Exception:
            return True

    def top_domains(self, limit: int = 10) -> list[dict]:
        """Ranks every domain that has ever reported an event, by total
        volume. Uses `SCAN` (via `scan_iter`), not `KEYS`: `KEYS` blocks the
        whole Redis instance for every other client while it walks the
        entire keyspace — exactly the kind of "scan under load" hazard the
        O(1) counters in this class exist to avoid in the first place, just
        moved from a growing list to the keyspace itself. `SCAN` is
        cursor-based and non-blocking.
        """
        domains: set[str] = set()

        for key in self._client.scan_iter(match=self._key("*", "total")):
            parts = key.split(":")

            # `*` in a Redis/fnmatch glob matches ":" too, so
            # "metrics:*:total" also matches the Sprint 249 bucket keys
            # ("metrics:{domain}:bucket:{hour}:total", 5 segments) — only
            # the plain per-scope counter ("metrics:{scope}:total", exactly
            # 3 segments) belongs in this ranking.
            if len(parts) != 3:
                continue

            scope = parts[1]

            # The global aggregate counter lives in the same "metrics:*:total"
            # keyspace as real domains — it must never show up as a ranked
            # "domain" itself (it would always rank #1, since it's the sum
            # of everything).
            if scope == self._GLOBAL_SCOPE:
                continue

            domains.add(scope)

        results = [self._read_scope(domain, domain) for domain in domains]
        results.sort(key=lambda item: item["total"], reverse=True)

        return results[:limit]

    def list(self) -> list[dict]:
        raise NotImplementedError(
            "AggregatedRedisMetricsStorage keeps only O(1) counters, not raw "
            "events — use summary() instead, or RedisMetricsStorage if raw "
            "event history is genuinely needed."
        )
