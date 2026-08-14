from app.platform.capabilities.capability_executor import CapabilityExecutor
from app.platform.capabilities.capability_manager_factory import (
    build_default_capability_manager,
)


def build_default_capability_executor() -> CapabilityExecutor:
    """Composition root for this executor. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_capability_manager()`, and wires it into a
    CapabilityExecutor — nothing else.
    """
    return CapabilityExecutor(manager=build_default_capability_manager())
