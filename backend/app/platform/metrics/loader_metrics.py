import time
from statistics import mean

from app.platform.metrics.alert_insights import AlertInsights
from app.platform.metrics.metrics_storage import InMemoryMetricsStorage, MetricsStorage


class LoaderMetricsStore:
    """Thin aggregation layer over a pluggable `MetricsStorage` — the
    in-memory/Redis/aggregated-Redis split lives entirely in
    `metrics_storage.py`; this class only knows how to turn a domain query
    into a summary, regardless of where the numbers came from.

    `domain=None` means "aggregate across every domain" — this is the
    unfiltered dashboard view `/cdn/metrics/summary` already serves to any
    authenticated caller, so it has to keep working for every storage
    backend, aggregated or not.
    """

    def __init__(self, storage: MetricsStorage | None = None):
        self._storage = storage or InMemoryMetricsStorage()

    @staticmethod
    def paginate(items: list, page: int = 1, per_page: int = 20) -> dict:
        """Generic pagination over an already-fetched, already-filtered
        list (Sprint 264) — `@staticmethod`, not the spec's own private
        `_paginate()`: nothing here touches `self`/`self._storage`, and
        an underscore-prefixed method meant to be called from the router
        (as every caller of this does) would repeat the exact "private
        attribute the router reaches into anyway" pattern already fixed
        for `store._storage`-reaching-through in prior sprints — every
        other router-facing capability on this class is a plain public
        method. Callable as `LoaderMetricsStore.paginate(...)` (no
        instance needed, e.g. from `/metrics/audit`, which has nothing
        else to do with a `LoaderMetricsStore`) or `store.paginate(...)`
        interchangeably.
        """
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page

        return {
            "items": items[start:end],
            "meta": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "has_next": end < total,
            },
        }

    def add(self, event: dict) -> None:
        self._storage.add(event)

    def summary(self, domain: str | None = None) -> dict:
        # Storages that maintain their own O(1) counters (e.g.
        # AggregatedRedisMetricsStorage) expose a `summary()` of their own —
        # prefer it over scanning `.list()`, which not every backend even
        # supports (AggregatedRedisMetricsStorage's `.list()` raises).
        aggregate = getattr(self._storage, "summary", None)
        if callable(aggregate):
            return aggregate(domain)

        return self._summary_from_events(self._storage.list(), domain)

    @staticmethod
    def _summary_from_events(events: list[dict], domain: str | None) -> dict:
        if domain:
            events = [e for e in events if e.get("domain") == domain]

        if not events:
            return {
                "domain": domain,
                "total": 0,
                "success": 0,
                "error": 0,
                "avg_duration": None,
                "error_rate": None,
            }

        success = [e for e in events if e.get("event") == "success"]
        error = [e for e in events if e.get("event") == "error"]
        durations = [e.get("duration") for e in success if e.get("duration") is not None]

        total = len(events)
        errors = len(error)

        return {
            "domain": domain,
            "total": total,
            "success": len(success),
            "error": errors,
            "avg_duration": mean(durations) if durations else None,
            "error_rate": (errors / total) if total else None,
        }

    def top_domains(self, limit: int = 10) -> list[dict]:
        """Only meaningful for storages that maintain their own per-domain
        ranking (AggregatedRedisMetricsStorage) — a scan-based backend has
        no efficient way to enumerate "every domain that ever reported an
        event" at all (InMemoryMetricsStorage/RedisMetricsStorage don't
        index by domain), so this returns an empty ranking there rather
        than attempting an expensive, unbounded scan just to build one.
        """
        ranker = getattr(self._storage, "top_domains", None)
        if not callable(ranker):
            return []

        domains = ranker(limit)

        for item in domains:
            item["health"] = self._health_score(item)

        return domains

    def domains_summary(self, domains: list[str]) -> list[dict]:
        """Per-domain stats for exactly the given domains — unlike
        `top_domains()`, which ranks across a storage's entire keyspace,
        this is safe to scope to "only the domains a specific tenant owns"
        (Sprint 248) without any risk of a low-traffic domain silently
        falling outside some global top-N cutoff. Works for every storage
        backend (reuses `summary()`, not `top_domains()`'s Redis-specific
        ranking), not just AggregatedRedisMetricsStorage.
        """
        items = [self.summary(domain) for domain in domains]

        for item in items:
            item["health_score"] = self._health_score(item)

        return items

    def domains_summary_window(self, domains: list[str], hours: int) -> list[dict]:
        """Same as `domains_summary()`, scoped to the last `hours` hours —
        only meaningful for storages that maintain time-bucketed counters
        (`AggregatedRedisMetricsStorage`). `InMemoryMetricsStorage`/
        `RedisMetricsStorage` don't track events by hour at all, so this
        returns an honest all-zero summary per domain there instead of an
        error.
        """
        windowed = getattr(self._storage, "summary_window", None)

        if callable(windowed):
            items = [windowed(domain, hours) for domain in domains]
        else:
            items = [
                {
                    "domain": domain,
                    "total": 0,
                    "success": 0,
                    "error": 0,
                    "avg_duration": None,
                    "error_rate": None,
                }
                for domain in domains
            ]

        for item in items:
            item["health_score"] = self._health_score(item)

        return items

    _SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def detect_anomalies(
        self,
        domains: list[str],
        resolve_tenant=None,
        get_alert_limit=None,
        background_tasks=None,
    ) -> list[dict]:
        """Flags a domain whose last 1h looks meaningfully worse than a
        baseline of the 24h *before* that hour (`offset=1`) — unlike
        Sprint 250's version, which compared against a 24h window that
        included the very hour being compared, diluting a spike into its
        own baseline instead of measuring it against clean prior data.

        When the storage has an `incident_manager` (Sprint 252), each
        anomalous domain is tracked through open/ongoing/resolved states
        instead of being debounced away from the response: an ongoing
        incident stays visible on every call (this is a status view, not a
        notification feed), while the *webhook* only fires once, on the
        transition into "open" — `incident_manager.open_or_update()`'s own
        status is what prevents repeat notifications, so Sprint 251's
        response-level debounce would now be redundant with it. Storages
        without an `incident_manager` configured fall back to that
        debounce, so a low-signal anomaly still doesn't clutter every
        single poll of this endpoint even without full incident tracking.

        `background_tasks` (a FastAPI `BackgroundTasks`, passed through
        from the router) makes the webhook send non-blocking; omitted (as
        every non-HTTP caller — tests, scripts — necessarily does), the
        webhook is sent inline/synchronously instead.

        `resolve_tenant` (Sprint 258) is an optional `domain -> tenant_id`
        callable (the router passes `resolver.get_owner`, the same
        `DomainTenantResolver` it already uses for scoping `domains`
        itself) — used to route a given alert through *that domain's own
        owning tenant's* configured channels. Per-domain, not a single
        tenant_id for the whole call: `domains` can span multiple tenants
        at once for an admin/global-scope caller (Sprint 254), so a flat
        `tenant_id` parameter (as the original spec's own
        `self._send_webhook(alert, tenant_id, ...)` call implied) would
        misroute every domain that isn't the caller's own. Omitted, no
        alert gets tenant-channel routing — `_send_webhook()` falls back
        to the shared single-webhook behavior from Sprint 256, unchanged.

        `get_alert_limit` (Sprint 265) is an optional `tenant_id -> int`
        callable — the router passes something like `lambda tid:
        container.auth().get_plan_limits(container.auth().
        get_organization_plan(tid)).get("alerts_per_hour", 5)` — used by
        `_send_webhook()` to rate-limit alert delivery against the
        *tenant's own plan*, not `AlertRateLimiter.allow()`'s hardcoded
        default. Same reasoning as `resolve_tenant`: a callable resolved
        per-alert by `_send_webhook()`, not a single value for the whole
        call, since `domains` can span multiple tenants (each on a
        different plan) for an admin/global-scope caller. Omitted, the
        rate limiter falls back to its own default limit, unchanged from
        Sprint 260.
        """
        results = []
        incident_manager = getattr(self._storage, "incident_manager", None)

        for domain in domains:
            current = self._window_or_empty(domain, hours=1, offset=0)
            baseline = self._window_or_empty(domain, hours=24, offset=1)

            if current["total"] == 0 or baseline["total"] == 0:
                continue

            error_spike = current["error_rate"] - baseline["error_rate"]
            latency_spike = (current["avg_duration"] or 0) - (baseline["avg_duration"] or 0)

            severity = self._severity(
                error_spike,
                latency_spike,
                current["total"],
                current["error_rate"],
                baseline["error_rate"],
            )

            if severity == "low":
                if incident_manager is not None:
                    incident_manager.resolve(domain, "error")
                    incident_manager.resolve(domain, "latency")
                continue

            alert = {
                "domain": domain,
                "type": self._alert_type(
                    error_spike, latency_spike, current["error_rate"], baseline["error_rate"]
                ),
                "severity": severity,
                "error_spike": error_spike,
                "latency_spike": latency_spike,
                "current": current,
                "baseline": baseline,
                # Never negative: a latency-only anomaly (latency_spike
                # > 300 with a flat or improved error rate) shouldn't
                # produce a negative "impact" that would otherwise sort
                # as if it were the largest in its severity tier.
                "impact": current["total"] * max(error_spike, 0),
                "ts": int(time.time()),
            }

            if incident_manager is not None:
                result = incident_manager.open_or_update(
                    domain, alert["type"], {"severity": severity}
                )
                alert["incident"] = result

                if result["status"] == "open":
                    tenant_id = resolve_tenant(domain) if resolve_tenant else None
                    self._send_webhook(
                        alert, tenant_id, background_tasks, get_alert_limit=get_alert_limit
                    )
            elif not self._should_emit_alert(f"{domain}:{severity}"):
                continue

            results.append(alert)

        results.sort(key=lambda alert: (self._SEVERITY_RANK[alert["severity"]], -alert["impact"]))

        return results

    def has_incident_tracking(self) -> bool:
        return getattr(self._storage, "incident_manager", None) is not None

    def get_active_incidents(self, domains: list[str]) -> list[dict]:
        """Currently-open-or-ongoing incidents for exactly the given
        domains — the authoritative, persisted state (`IncidentManager`'s
        own active records), not a fresh recomputation the way
        `detect_anomalies()`'s returned alerts are. `[]` for storages with
        no `incident_manager` configured, not an error.
        """
        incident_manager = getattr(self._storage, "incident_manager", None)
        if incident_manager is None:
            return []

        items = []
        for domain in domains:
            items.extend(incident_manager.get_active(domain))

        items.sort(
            key=lambda item: (
                self._SEVERITY_RANK.get(item.get("severity"), len(self._SEVERITY_RANK)),
                -item.get("started_at", 0),
            )
        )

        return items

    def get_time_series(self, domain: str, hours: int = 24) -> list[dict]:
        """Chart-ready hourly time series (Sprint 263) — one entry per
        hour, oldest first, each computed via `_window_or_empty()`
        (Sprint 249), not a new `hasattr(self._storage, "summary_window")`
        + direct `self._storage.summary_window(...)` call as the spec's
        own version had: that duplicates a check `_window_or_empty()`
        already does (via the established `getattr`/`callable` capability
        pattern, not `hasattr`), and unconditionally returning `[]` for a
        non-windowing storage is inconsistent with how this same "storage
        doesn't support summary_window" case is already handled elsewhere
        (`domains_summary_window()`, Sprint 249 — "an honest all-zero
        summary per domain... not an error"). Here, that means `hours`
        zeroed entries instead of an empty chart with no data points at
        all.

        Also fixes a real bug in the spec's own version: it read
        `bucket.get("errors", 0)` (plural) — `summary_window()`/
        `_window_or_empty()` both key their error count `"error"`
        (singular; matches `summary()`'s own shape). Read literally, the
        chart's error count would always silently be `0`, contradicting
        its own `error_rate` values on the same data point.
        """
        data = []

        for offset in range(hours):
            bucket = self._window_or_empty(domain, hours=1, offset=offset)
            data.append(
                {
                    "hour_offset": offset,
                    "total": bucket.get("total", 0),
                    "errors": bucket.get("error", 0),
                    "avg_duration": bucket.get("avg_duration"),
                    "error_rate": bucket.get("error_rate"),
                }
            )

        return list(reversed(data))

    def get_top_incidents(self, domains: list[str]) -> list[dict]:
        """Up to 10 highest-priority active incidents (Sprint 263) —
        reuses `get_active_incidents()`'s already-authoritative state,
        never recomputes anomalies.

        The spec's own secondary sort key, `x.get("current", {}).get(
        "error_rate", 0)`, is dead code: `IncidentManager`'s persisted
        records are built from `open_or_update(domain, alert_type,
        {"severity": severity})` (see `detect_anomalies()`) — only
        `severity` (plus whatever `IncidentManager` itself adds, e.g.
        `domain`/`type`/`started_at`) ever gets stored; there is no
        `"current"` key on an active-incident record, so that lookup
        always silently fell back to `0` for every incident, meaning
        ties within the same severity were never actually broken by
        error rate at all. Fixed with `started_at` instead — a field
        that genuinely exists on every incident record (the same one
        `get_active_incidents()` itself already sorts by), giving a real
        tiebreak ("most recently started, within the same severity,
        first") without recomputing anything.
        """
        incidents = self.get_active_incidents(domains)
        severity_weight = {"critical": 3, "high": 2, "medium": 1, "low": 0}

        return sorted(
            incidents,
            key=lambda item: (
                severity_weight.get(item.get("severity"), 0),
                item.get("started_at", 0),
            ),
            reverse=True,
        )[:10]

    def get_live_status(self, domains: list[str]) -> dict[str, str]:
        """Per-domain live status (Sprint 263): `"healthy"` by default,
        `"degraded"` for an active `high`-severity incident, `"critical"`
        for an active `critical`-severity one (critical always wins over
        degraded, regardless of processing order). Reuses
        `get_active_incidents()` — no new anomaly computation.

        `status.get(domain)` (not the spec's own `status[domain]`) in the
        `elif` check: defensive against an incident whose `domain` isn't
        actually a member of the `domains` list this method itself was
        called with (shouldn't happen given how `get_active_incidents()`
        fetches incidents strictly per-domain from that same list, but a
        direct `status[domain]` read would `KeyError` instead of just
        being harmlessly wrong if that assumption is ever violated).
        """
        incidents = self.get_active_incidents(domains)
        status = {domain: "healthy" for domain in domains}

        for incident in incidents:
            domain = incident.get("domain")
            severity = incident.get("severity")

            if severity == "critical":
                status[domain] = "critical"
            elif severity == "high" and status.get(domain) != "critical":
                status[domain] = "degraded"

        return status

    def get_alert_insights(self, domains: list[str]) -> dict:
        """Aggregate business-facing view over `get_active_incidents()`'s
        already-authoritative state (Sprint 261) — reads only, generates
        or fetches nothing new (`detect_anomalies()` is untouched by this
        sprint). `{}`-safe defaults throughout via `get_active_incidents()`
        itself, which already returns `[]` for storages with no
        `incident_manager` configured.

        The spec's own version guarded this call behind
        `if hasattr(self, "get_active_incidents")` — always `True`
        (`get_active_incidents` is a real method defined on this very
        class, not an optional capability on the storage), so that check
        never actually did anything; removed rather than kept as
        misleading dead code.
        """
        incidents = self.get_active_incidents(domains)

        return {
            "top_domains": AlertInsights.top_domains_by_alerts(incidents),
            "severity_distribution": AlertInsights.severity_distribution(incidents),
            "affected_domains": AlertInsights.affected_domains(incidents),
            "total_incidents": len(incidents),
        }

    def get_health_score(self, domains: list[str]) -> int:
        """Business-facing "customer health" score (Sprint 262) — 100
        minus a per-severity-weighted penalty for every currently active
        incident, floored at 0. Not the same thing as the existing
        `_health_score()` staticmethod below (Sprint 247): that one
        scores a *single domain's* traffic (error rate + latency vs.
        baseline) for `/metrics/dashboard`'s per-domain ranking; this one
        scores the *caller's overall incident load* across every domain
        they can see, for an executive-level "how healthy is this
        customer" number.

        Self-contained (computes its own `get_alert_insights()`) so it
        stays usable on its own; `get_dashboard_data()` uses
        `_health_score_from_insights()` instead with its own
        already-computed insights, specifically to avoid calling
        `get_active_incidents()` a second time for the same request (see
        that method, and this sprint's own "don't compute alerts again"
        constraint — the spec's own version called `get_health_score()`
        from inside `get_dashboard_data()`, silently doubling that work).
        """
        return self._health_score_from_insights(self.get_alert_insights(domains))

    _SEVERITY_WEIGHT = {"critical": 5, "high": 3, "medium": 2, "low": 1}

    @classmethod
    def _health_score_from_insights(cls, insights: dict) -> int:
        score = 100

        for severity, count in insights["severity_distribution"].items():
            score -= count * cls._SEVERITY_WEIGHT.get(severity, 1)

        return max(score, 0)

    def get_dashboard_data(self, domains: list[str], tenant_id: str | None = None) -> dict:
        """Unified dashboard aggregate (Sprint 262) — combines
        `get_alert_insights()`, digest pending-count, the platform's
        overall traffic `summary()`, and a business health score, without
        computing any of them a second way: every field here is read
        through an existing `LoaderMetricsStore` method, nothing reaches
        into `self._storage` directly.

        `summary` is always `self.summary()` (no domain filter — the
        platform-wide total), for every scope, tenant or global: the
        spec's own version called `self._storage.summary(domains)`
        directly, passing a *list* where `AggregatedRedisMetricsStorage.
        summary(domain: str | None)` expects a single domain string or
        `None` — the list itself is truthy, so it would silently become
        the Redis key's scope segment (`metrics:['a.com', 'b.com']:total`,
        never matching real data) instead of being treated as "no
        filter"; worse, for a tenant with an *empty* domains list (no
        organization at all), an empty list is falsy, so `scope` would
        fall through to the platform-wide global key, leaking cross-
        tenant totals to exactly the caller `_resolve_metrics_scope()`
        is supposed to keep tenant-scoped. `self.summary()` (no args)
        already means "platform-wide total" — the same, already-accepted
        behavior `/metrics/summary` (Sprint 236) has always had for any
        authenticated caller with no `domain` filter — so this reuses
        that existing, correct method instead of a broken new call.

        `digest_size` stays `0` when `tenant_id` is falsy (the
        admin/global-scope case, or a caller with no organization at
        all) — a digest is inherently per-tenant, there's no single
        "global digest" to report.
        """
        insights = self.get_alert_insights(domains)
        digest_size = self.get_digest_size(tenant_id) if tenant_id else 0

        return {
            "insights": insights,
            "digest": {"pending": digest_size},
            "summary": self.summary(),
            "health_score": self._health_score_from_insights(insights),
        }

    @staticmethod
    def _alert_type(
        error_spike: float, latency_spike: float, current_error: float, baseline_error: float
    ) -> str:
        """Mirrors `_severity()`'s own branch order/thresholds exactly, so
        an incident is always typed by whichever condition actually
        classified its severity — not an independent heuristic (e.g. "type
        is error if error_spike > 0, else latency") that could disagree
        with that classification and mislabel, say, a latency-driven
        incident as an error one because error_spike also happened to be
        slightly positive.
        """
        if current_error > max(0.3, baseline_error * 2):
            return "error"
        if latency_spike > 300:
            return "latency"
        if error_spike > 0.2:
            return "error"
        return "unknown"

    def _send_webhook(
        self,
        alert: dict,
        tenant_id: str | None,
        background_tasks=None,
        get_alert_limit=None,
    ) -> None:
        """When the storage has a `webhook_queue` (Sprint 256), the alert
        is enqueued (persisted, survives a process restart) and a drain of
        that queue is scheduled right away — same non-blocking mechanism
        as before (`background_tasks.add_task`, falling back to inline
        when there's no request in flight), but now going through
        `WebhookQueue`/`WebhookWorker`'s retry/dead-letter handling instead
        of a single fire-and-forget send. A delivery that fails here isn't
        lost: it's requeued (up to 3 attempts) and picked up again by the
        next alert's drain, or by the admin-triggered
        `POST /metrics/webhook/process`.

        Storages configured the Sprint 252 way (`webhook=`, no queue) keep
        working exactly as before — full backward compatibility, not a
        breaking change to that wiring.

        Multi-channel routing (Sprint 258): when the storage also has a
        `channel_manager` *and* a `tenant_id` was resolved for this
        specific alert, one item is enqueued per active channel configured
        for that tenant+severity, each carrying its own destination URL
        (`WebhookQueue.enqueue(..., url=...)`) and its own template
        (`_format_payload()`). No active channels for this tenant (the
        common case — most storages/tenants have none configured, and
        every pre-Sprint-258 test's storage has no `channel_manager` at
        all) falls straight back to the original Sprint 256 behavior:
        the raw `alert` enqueued once, delivered to the queue's single
        shared `get_url()` target.

        Silencing + cooldown (Sprint 259): checked first, ahead of every
        delivery mechanism below (queue-based or the plain `webhook`
        fallback) — a silenced domain or a cooldown-blocked domain+type
        gets no webhook at all, through any path. Neither touches
        incident tracking or this alert's own structure: the incident
        was already opened/updated by the caller before `_send_webhook()`
        was ever invoked, and the alert still appears in
        `/metrics/alerts`/`/metrics/incidents` — only the outbound
        notification is suppressed.

        Rate limiting + digest (Sprint 260): checked *after* silence/
        cooldown, not before (the spec's own "at the very top" ordering)
        — a domain the admin has explicitly silenced must not still leak
        into a digest just because it also happens to be noisy; silence
        is a deliberate "tell me nothing about this" action and should
        take priority over "batch it for later." A domain that's rate-
        limited but not silenced gets its alert added to that domain's
        owning tenant's digest instead of dropped outright, so bursty
        traffic still surfaces eventually via `POST /metrics/alerts/
        digest/flush` rather than going missing. Uses the `tenant_id`
        already resolved for this alert (the same one channel routing
        above uses) — not a fresh `resolve_tenant(...)` call, which isn't
        even in scope here (only `detect_anomalies()` holds that
        callable; `_send_webhook()` only ever receives its result).

        Plan-based alert limit (Sprint 265): when `get_alert_limit` and
        `tenant_id` are both available, the rate limiter's `limit` comes
        from the tenant's own plan instead of `AlertRateLimiter.allow()`'s
        hardcoded default — a Free-plan tenant genuinely gets a lower
        ceiling than an Enterprise one. `-1` (this platform's established
        "unlimited" sentinel — `PlatformAuth.check_limit()` already
        treats it the same way) skips the rate-limit check entirely
        rather than being passed through to `AlertRateLimiter.allow()`,
        which has no notion of that sentinel itself (it would otherwise
        read `current <= -1` as "never allowed", the opposite of
        unlimited) — deliberately kept out of `AlertRateLimiter`, which
        stays a generic, plan-unaware rate limiter.
        """
        controls = getattr(self._storage, "alert_controls", None)
        if controls is not None:
            if controls.is_silenced(alert["domain"]):
                return

            alert_type = alert.get("type", "unknown")
            if not controls.allow_alert(alert["domain"], alert_type, cooldown=300):
                return

        # Usage tracking (Sprint 270) — recorded once an alert has passed
        # silence/cooldown (a domain the admin deliberately silenced
        # generates no billable notification), but *before* the rate-
        # limit check below: for a future overage-billing feature, volume
        # that exceeded the plan's rate limit is exactly the volume that
        # matters, not just what was successfully delivered in real time.
        # Pure observability for now — nothing here blocks delivery; see
        # `get_usage_limit()` (platform_auth.py) for the plan-limit
        # lookup this is meant to eventually be enforced against.
        usage_tracker = getattr(self._storage, "usage_tracker", None)
        if usage_tracker is not None and tenant_id is not None:
            usage_tracker.increment(tenant_id, "alerts_sent")

        rate_limiter = getattr(self._storage, "rate_limiter", None)
        if rate_limiter is not None:
            if get_alert_limit is not None and tenant_id is not None:
                limit = get_alert_limit(tenant_id)
                allowed = limit == -1 or rate_limiter.allow(alert["domain"], limit=limit)
            else:
                allowed = rate_limiter.allow(alert["domain"])

            if not allowed:
                digest = getattr(self._storage, "alert_digest", None)
                if digest is not None and tenant_id is not None:
                    digest.add(tenant_id, alert)
                return

        webhook_queue = getattr(self._storage, "webhook_queue", None)
        if webhook_queue is not None:
            channel_manager = getattr(self._storage, "channel_manager", None)
            channels = (
                channel_manager.get_active_channels(
                    tenant_id, alert["severity"], alert.get("type")
                )
                if channel_manager is not None and tenant_id is not None
                else []
            )

            if channels:
                for channel in channels:
                    payload = self._format_payload(alert, channel.get("type"))
                    webhook_queue.enqueue(payload, url=channel.get("url"))
            else:
                webhook_queue.enqueue(alert)

            worker = getattr(self._storage, "webhook_worker", None)
            if worker is not None:
                if background_tasks is not None:
                    background_tasks.add_task(worker.process)
                else:
                    worker.process()

            return

        webhook = getattr(self._storage, "webhook", None)
        if webhook is None:
            return

        if background_tasks is not None:
            background_tasks.add_task(webhook.send, alert)
        else:
            webhook.send(alert)

    @staticmethod
    def _format_payload(alert: dict, channel_type: str | None) -> dict:
        from app.platform.metrics.alert_formatter import format_generic, format_slack

        if channel_type == "slack":
            return format_slack(alert)

        return format_generic(alert)

    def add_alert_channel(self, tenant_id: str, channel: dict) -> dict | None:
        """`None` when there's no `channel_manager` configured — the
        router turns that into a 503, same convention as
        `set_webhook_url()`. Delegates rather than exposing
        `self._storage.channel_manager` for callers (the router) to reach
        into directly: the same private-attribute-reach-through this
        module's `getattr`/`callable` capability pattern exists to avoid.
        """
        manager = getattr(self._storage, "channel_manager", None)
        if manager is None:
            return None

        return manager.add_channel(tenant_id, channel)

    def get_alert_channels(self, tenant_id: str) -> list[dict]:
        manager = getattr(self._storage, "channel_manager", None)
        if manager is None:
            return []

        return manager.get_channels(tenant_id)

    def remove_alert_channel(self, tenant_id: str, channel_id: str) -> bool:
        """`False` when there's no `channel_manager` configured — the
        router turns that into a 503."""
        manager = getattr(self._storage, "channel_manager", None)
        if manager is None:
            return False

        manager.remove_channel(tenant_id, channel_id)
        return True

    def silence_alert(self, domain: str, seconds: int) -> bool:
        """`False` when there's no `alert_controls` configured — the
        router turns that into a 503, same convention as
        `set_webhook_url()`. Delegates rather than exposing
        `self._storage.alert_controls` for the router to reach into
        directly.
        """
        controls = getattr(self._storage, "alert_controls", None)
        if controls is None:
            return False

        controls.silence(domain, seconds)
        return True

    def unsilence_alert(self, domain: str) -> bool:
        """`False` when there's no `alert_controls` configured — same
        convention as `silence_alert()`."""
        controls = getattr(self._storage, "alert_controls", None)
        if controls is None:
            return False

        controls.unsilence(domain)
        return True

    def list_silenced_alerts(self) -> list[str]:
        """`[]` when there's no `alert_controls` configured — a read, so
        it degrades gracefully rather than 503ing, matching
        `get_alert_channels()`'s own convention."""
        controls = getattr(self._storage, "alert_controls", None)
        if controls is None:
            return []

        return controls.list_silenced()

    def flush_alert_digest(self, tenant_id: str) -> list[dict]:
        """`[]` when there's no `alert_digest` configured, or when the
        tenant's digest is empty — a read, so it degrades gracefully
        rather than 503ing, matching `get_alert_channels()`'s own
        convention. Otherwise, a single synthetic "digest" summary
        object (never more than one — this isn't a list of individual
        alerts, it's one grouped batch), with `domains` deduplicated and
        sorted for a deterministic result rather than relying on
        `set()`'s own iteration order (the same "never dependent on set/
        dict iteration order" care already taken by `/metrics/dashboard`'s
        sort-tiebreak).
        """
        digest = getattr(self._storage, "alert_digest", None)
        if digest is None:
            return []

        alerts = digest.flush(tenant_id)
        if not alerts:
            return []

        return [
            {
                "type": "digest",
                "count": len(alerts),
                "domains": sorted({a["domain"] for a in alerts}),
                "alerts": alerts,
            }
        ]

    def get_digest_size(self, tenant_id: str) -> int:
        """`0` when there's no `alert_digest` configured — a read-only
        peek at how many alerts are pending for a tenant, without
        flushing them (unlike `flush_alert_digest()`). Delegates rather
        than exposing `self._storage.alert_digest` for the router to
        reach into directly: the same private-attribute-reach-through
        this module's `getattr`/`callable` capability pattern exists to
        avoid, for `GET /metrics/alerts/digest` (Sprint 261) the same as
        every other endpoint since Sprint 251.
        """
        digest = getattr(self._storage, "alert_digest", None)
        if digest is None:
            return 0

        return digest.size(tenant_id)

    def get_usage(self, tenant_id: str, metric: str) -> int:
        """`0` when there's no `usage_tracker` configured — same "optional
        capability, no crash" convention as every other read here.
        Delegates rather than exposing `self._storage.usage_tracker` for
        the router to reach into directly (Sprint 270's own explicit
        "don't access `_storage` in the router" rule).
        """
        usage_tracker = getattr(self._storage, "usage_tracker", None)
        if usage_tracker is None:
            return 0

        return usage_tracker.get(tenant_id, metric)

    def set_webhook_url(self, url: str) -> bool:
        """`True` if the storage has a `webhook_queue` configured to set
        the URL on (i.e. Redis is available), `False` otherwise — the
        router turns a `False` into a 503, matching the "optional
        capability, no crash" convention used throughout this module.
        """
        queue = getattr(self._storage, "webhook_queue", None)
        if queue is None:
            return False

        queue.set_url(url)
        return True

    def webhook_queue_status(self) -> dict:
        queue = getattr(self._storage, "webhook_queue", None)
        if queue is None:
            return {"configured": False, "queue_size": 0, "failed_count": 0}

        return {
            "configured": True,
            "queue_size": queue.queue_size(),
            "failed_count": queue.failed_count(),
        }

    def process_webhook_queue(self, limit: int = 10) -> dict | None:
        """`None` when there's no `webhook_worker` configured — the router
        turns that into a 503, same convention as `set_webhook_url()`.
        """
        worker = getattr(self._storage, "webhook_worker", None)
        if worker is None:
            return None

        return worker.process(limit)

    def webhook_metrics(self) -> dict:
        """Delivery observability (Sprint 257) — zeroed, not an error, when
        no `webhook_queue` is configured, matching every other optional-
        capability method in this class."""
        queue = getattr(self._storage, "webhook_queue", None)
        if queue is None:
            return {"sent": 0, "success": 0, "failed": 0, "retry": 0, "success_rate": 0.0}

        return queue.metrics()

    def get_incident_history(self, domains: list[str], limit: int = 100) -> list[dict]:
        """Per-domain incident history for exactly the given domains —
        mirrors `domains_summary()`'s scoping shape. `[]` for storages with
        no `incident_manager` configured, not an error.
        """
        incident_manager = getattr(self._storage, "incident_manager", None)
        if incident_manager is None:
            return []

        items = []
        for domain in domains:
            items.extend(incident_manager.get_history(domain, limit))

        items.sort(key=lambda item: item.get("resolved_at", 0), reverse=True)

        return items[:limit]

    def _window_or_empty(self, domain: str, hours: int, offset: int) -> dict:
        windowed = getattr(self._storage, "summary_window", None)
        if callable(windowed):
            return windowed(domain, hours, offset)

        return {
            "domain": domain,
            "total": 0,
            "success": 0,
            "error": 0,
            "avg_duration": None,
            "error_rate": None,
        }

    def _should_emit_alert(self, key: str) -> bool:
        """Delegates to the storage's own debounce, when it has one
        (`AggregatedRedisMetricsStorage.should_emit_alert()`), rather than
        reaching into a storage-private attribute (e.g. its Redis client)
        directly from here — same `getattr`/`callable` capability-check
        pattern already used for `summary`/`top_domains`/`summary_window`.
        Storages with no debounce capability never suppress an alert.
        """
        debounce = getattr(self._storage, "should_emit_alert", None)
        if not callable(debounce):
            return True

        return debounce(key)

    @staticmethod
    def _severity(
        error_spike: float,
        latency_spike: float,
        volume: int,
        current_error: float,
        baseline_error: float,
    ) -> str:
        """`"low"` (not an anomaly at all) is also `detect_anomalies()`'s
        own cutoff — a single set of thresholds, not one gate plus a
        separate classifier that could silently drift out of sync with it.
        Latency is in milliseconds, matching what the loader reports
        (Sprint 240). Thresholds are fixed for now, not configurable per
        domain/tenant — a known, intentional limitation for this sprint.

        Volume-aware (Sprint 251): fewer than 20 events in the last hour is
        too small a sample for a percentage-based error rate to mean
        anything (2 requests, 1 failing, "looks like" a 50% error rate) —
        treated as `low` regardless of how extreme the rate looks.
        Combines a relative check (current error rate at least double the
        baseline) with an absolute floor (at least 30%) so a spike off a
        near-zero baseline doesn't get flagged from a single failure.
        """
        if volume < 20:
            return "low"

        if current_error > max(0.3, baseline_error * 2):
            return "critical" if current_error > 0.5 else "high"

        if latency_spike > 300:
            return "high"

        if error_spike > 0.2:
            return "medium"

        return "low"

    @staticmethod
    def _health_score(item: dict) -> float:
        """0-100 — penalizes error rate and above-baseline latency (50ms
        treated as the no-penalty baseline; the loader reports duration in
        milliseconds). A domain with no successful-duration data at all
        (e.g. 100% error rate — precisely the domain most in need of
        attention here) contributes zero latency penalty rather than
        crashing the whole ranking on a `None / 50` division; its error
        rate alone already drives the score down. Clamped to [0, 100] so a
        malformed/negative self-reported `duration` (the ingestion endpoint
        is unauthenticated and doesn't validate it) can't push a score
        outside the scale it's supposed to represent.
        """
        error_rate = item.get("error_rate") or 0
        avg_duration = item.get("avg_duration")

        error_penalty = error_rate * 100
        latency_penalty = min(avg_duration / 50, 100) if avg_duration is not None else 0

        score = 100 - error_penalty - latency_penalty

        return max(0.0, min(100.0, score))
