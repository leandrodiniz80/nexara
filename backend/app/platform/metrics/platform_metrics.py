class PlatformMetrics:
    def __init__(self):
        self._counters: dict[str, dict[str | None, int]] = {}
        self._timings: dict[str, dict[str | None, list[float]]] = {}

    def increment(self, name: str, value: int = 1, organization_id: str | None = None) -> None:
        buckets = self._counters.setdefault(name, {})
        buckets[organization_id] = buckets.get(organization_id, 0) + value

    def timing(
        self, name: str, duration: float, organization_id: str | None = None
    ) -> None:
        buckets = self._timings.setdefault(name, {})
        buckets.setdefault(organization_id, []).append(duration)

    def get_metrics(self, organization_id: str | None = None) -> dict:
        if organization_id is not None:
            counters = {
                name: buckets[organization_id]
                for name, buckets in self._counters.items()
                if organization_id in buckets
            }
            timing_values = {
                name: buckets[organization_id]
                for name, buckets in self._timings.items()
                if buckets.get(organization_id)
            }
        else:
            counters = {name: sum(buckets.values()) for name, buckets in self._counters.items()}
            timing_values = {
                name: [value for values in buckets.values() for value in values]
                for name, buckets in self._timings.items()
            }
            timing_values = {name: values for name, values in timing_values.items() if values}

        timings = {
            name: {
                "count": len(values),
                "avg": sum(values) / len(values),
                "max": max(values),
            }
            for name, values in timing_values.items()
        }

        return {"counters": counters, "timings": timings}
