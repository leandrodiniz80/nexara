from app.platform.capabilities.capability_manager import CapabilityManager
from app.platform.capabilities.capability_registry_factory import (
    build_default_capability_registry,
)


def build_default_capability_manager() -> CapabilityManager:
    """Composition root for this manager. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_capability_registry()`, and wires it into a
    CapabilityManager — nothing else.
    """
    return CapabilityManager(registry=build_default_capability_registry())
