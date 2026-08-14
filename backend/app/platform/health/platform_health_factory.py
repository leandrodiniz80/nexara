from app.platform.health.health_report_service_factory import (
    build_default_health_report_service,
)
from app.platform.health.platform_health import PlatformHealth


def build_default_platform_health() -> PlatformHealth:
    """Composition root for this facade. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_health_report_service()`, and wires it into a
    PlatformHealth — nothing else.
    """
    return PlatformHealth(health_report_service=build_default_health_report_service())
