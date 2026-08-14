from app.platform.health.health_coordinator_factory import build_default_health_coordinator
from app.platform.health.platform_health_facade import PlatformHealthFacade


def build_default_platform_health_facade() -> PlatformHealthFacade:
    """Composition root for this facade. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_health_coordinator()`, and wires it into a
    PlatformHealthFacade — nothing else.
    """
    return PlatformHealthFacade(health_coordinator=build_default_health_coordinator())
