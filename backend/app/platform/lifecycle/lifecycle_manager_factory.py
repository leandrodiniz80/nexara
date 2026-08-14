from app.platform.lifecycle.lifecycle_manager import LifecycleManager
from app.platform.lifecycle.lifecycle_participant_registry_factory import (
    build_default_lifecycle_participant_registry,
)


def build_default_lifecycle_manager() -> LifecycleManager:
    """Composition root for this manager. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_lifecycle_participant_registry()`, and wires it into a
    LifecycleManager — nothing else.
    """
    return LifecycleManager(registry=build_default_lifecycle_participant_registry())
