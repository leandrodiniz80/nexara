from app.platform.health.health_monitor import HealthMonitor
from app.platform.health.platform_health_factory import build_default_platform_health


def build_default_health_monitor() -> HealthMonitor:
    """Composition root for this monitor. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_platform_health()`, and wires it into a HealthMonitor
    — nothing else.
    """
    return HealthMonitor(platform_health=build_default_platform_health())
