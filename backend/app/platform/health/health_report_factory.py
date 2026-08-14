from app.platform.health.health_report import HealthReport


def build_health_report(results: tuple[bool, ...]) -> HealthReport:
    """Composition root for this report. Computes `healthy` as `all(results)`
    and wires both into a HealthReport — nothing else.
    """
    return HealthReport(results=results, healthy=all(results))
