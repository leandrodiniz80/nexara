def build_upgrade_message(level: str, used: int, limit: int) -> str | None:
    """Sprint 271's own Part 4 defined this but never actually wired it
    into anything — `check_threshold()` below calls it directly, so the
    endpoint's response always includes a ready-to-display message,
    matching the sprint's own stated UX/monetization goal.
    """
    if level == "warning":
        return f"Você já usou {used}/{limit} alertas. Considere upgrade."

    if level == "hard_limit":
        return f"Limite atingido ({used}/{limit}). Faça upgrade para continuar."

    return None


class UsageAlerts:
    """Soft-limit / upgrade-nudge signaling (Sprint 271) — pure
    computation, no storage of its own, no blocking side effects
    anywhere: `check_threshold()` only ever *reports* where a tenant
    stands relative to their plan, never gates anything (see
    `_send_webhook()` in loader_metrics.py, deliberately untouched by
    this sprint — see below).

    Takes `get_usage`/`get_limit` as plain callables
    (`(tenant_id, metric) -> int`), not whole `usage_tracker`/`auth`
    objects (the spec's own `__init__(self, usage_tracker, auth)`) — the
    same "inject a callable, not a dependency" shape already established
    for `resolve_tenant`/`get_alert_limit` (Sprint 258/265). This is what
    lets the router construct it as `UsageAlerts(store.get_usage,
    container.auth().get_usage_limit)` without ever reaching into
    `store._storage` (this sprint's own explicit rule) or wiring a new
    `PlatformAuth` dependency into the metrics-storage construction path
    (`app/api/dependencies/metrics.py`'s `_create_storage()` has no
    access to `container`/`PlatformAuth` at all — it's a lazy,
    process-wide singleton built with no per-request context, unlike the
    router, which already has both `container.auth()` and `store`
    injected). Wiring `usage_alerts` as a *storage* capability, as the
    spec's own Part 5 proposed, would have required a genuinely new
    cross-subsystem coupling (metrics storage knowing about auth) this
    sprint doesn't actually need, since nothing here reads Redis directly
    anyway.
    """

    def __init__(self, get_usage, get_limit):
        self._get_usage = get_usage
        self._get_limit = get_limit

    def check_threshold(
        self, tenant_id: str, usage_metric: str, limit_metric: str | None = None
    ) -> dict | None:
        """`usage_metric`/`limit_metric` are deliberately separate keys,
        not one shared `metric` (the spec's own signature). The two
        systems this class bridges use different names for the same
        real-world quantity: `UsageTracker` (Sprint 270) tracks alerts
        sent under `"alerts_sent"`, while `PlatformAuth`'s plan limits
        (Sprint 265) store the cap under `"alerts_per_hour"`. A single
        shared `metric` would make `get_limit(tenant_id, "alerts_sent")`
        miss that key in the plan-limits dict, silently fall back to its
        own `-1` ("unlimited") default, and mean this method could never
        actually fire — defeating the sprint's purpose the same way
        Sprint 270's own `get_usage_limit()` bug once did. Defaults
        `limit_metric` to `usage_metric` so callers where both systems
        happen to share one key can still call this with a single name.
        """
        if limit_metric is None:
            limit_metric = usage_metric

        limit = self._get_limit(tenant_id, limit_metric)

        if limit == -1:
            return None

        used = self._get_usage(tenant_id, usage_metric)

        # `limit == 0` (a plan that disallows a metric entirely) is not
        # exercised by any current plan, but `used / limit` would raise
        # ZeroDivisionError if it ever were — any usage at all against a
        # zero limit is unambiguously "at the hard limit", not "no
        # signal at all" (the spec's own `if limit else 0` would produce).
        ratio = (used / limit) if limit else (1.0 if used > 0 else 0.0)

        if ratio >= 1.0:
            return {
                "level": "hard_limit",
                "used": used,
                "limit": limit,
                "message": build_upgrade_message("hard_limit", used, limit),
            }

        if ratio >= 0.8:
            return {
                "level": "warning",
                "used": used,
                "limit": limit,
                "message": build_upgrade_message("warning", used, limit),
            }

        return None
