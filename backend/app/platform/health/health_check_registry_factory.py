from app.platform.health.health_check_registry import HealthCheckRegistry


def build_default_health_check_registry() -> HealthCheckRegistry:
    """Composition root for this registry. Returns an empty registry — no
    concrete HealthCheck exists yet to register.
    """
    return HealthCheckRegistry()
