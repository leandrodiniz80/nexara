from app.platform.health.health_executor import HealthExecutor
from app.platform.health.health_manager_factory import build_default_health_manager


def build_default_health_executor() -> HealthExecutor:
    """Composition root for this executor. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_health_manager()`, and wires it into a HealthExecutor
    — nothing else.
    """
    return HealthExecutor(manager=build_default_health_manager())
