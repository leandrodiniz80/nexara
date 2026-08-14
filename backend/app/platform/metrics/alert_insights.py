class AlertInsights:
    """Pure aggregation over an already-fetched list of incidents — reads
    nothing itself (no `store`/storage dependency: every method takes
    `incidents` as an explicit argument), matching this sprint's own
    constraint of only reading from existing systems, never generating or
    fetching data of its own. `LoaderMetricsStore.get_alert_insights()`
    is the one place that actually calls `get_active_incidents()`.

    Static methods, not instance methods on a `self._store`-holding
    object (the spec's own `__init__(self, store)`): none of the three
    methods below ever reference `self` or a store — an unused
    constructor parameter/attribute would just be dead coupling to
    nothing, the same "don't carry state a class never uses" reasoning
    already applied elsewhere in this module (e.g. `_severity()`/
    `_health_score()` on `LoaderMetricsStore` itself are `@staticmethod`
    for the same reason).
    """

    @staticmethod
    def top_domains_by_alerts(incidents: list[dict]) -> list[dict]:
        counter: dict[str, int] = {}

        for incident in incidents:
            domain = incident.get("domain")
            counter[domain] = counter.get(domain, 0) + 1

        # Deterministic tiebreak (domain name) for equal counts, not just
        # whatever order `counter.items()` happens to iterate in — same
        # "never dependent on iteration order alone" care already taken
        # by `/metrics/dashboard`'s own sort.
        return sorted(
            [{"domain": domain, "count": count} for domain, count in counter.items()],
            key=lambda item: (-item["count"], item["domain"] or ""),
        )[:10]

    @staticmethod
    def severity_distribution(incidents: list[dict]) -> dict[str, int]:
        distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for incident in incidents:
            severity = incident.get("severity")
            if severity in distribution:
                distribution[severity] += 1

        return distribution

    @staticmethod
    def affected_domains(incidents: list[dict]) -> int:
        return len({incident.get("domain") for incident in incidents})
