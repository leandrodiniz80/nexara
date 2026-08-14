from app.platform.health.health_check_registry_factory import (
    build_default_health_check_registry,
)
from app.platform.health.health_manager import HealthManager


def build_default_health_manager() -> HealthManager:
    """Composition root for this manager. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_health_check_registry()`, and wires it into a
    HealthManager — nothing else.
    """
    return HealthManager(registry=build_default_health_check_registry())
