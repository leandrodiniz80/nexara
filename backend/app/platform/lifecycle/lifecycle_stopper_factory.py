from app.platform.lifecycle.lifecycle_manager_factory import build_default_lifecycle_manager
from app.platform.lifecycle.lifecycle_stopper import LifecycleStopper


def build_default_lifecycle_stopper() -> LifecycleStopper:
    """Composition root for this stopper. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_lifecycle_manager()`, and wires it into a
    LifecycleStopper — nothing else.
    """
    return LifecycleStopper(manager=build_default_lifecycle_manager())
