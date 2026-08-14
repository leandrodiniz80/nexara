from app.platform.health.health_coordinator import HealthCoordinator
from app.platform.health.health_monitor_factory import build_default_health_monitor


def build_default_health_coordinator() -> HealthCoordinator:
    """Composition root for this coordinator. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_health_monitor()`, and wires it into a
    HealthCoordinator — nothing else.
    """
    return HealthCoordinator(health_monitor=build_default_health_monitor())
