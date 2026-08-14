from app.platform.lifecycle.lifecycle_manager_factory import build_default_lifecycle_manager
from app.platform.lifecycle.lifecycle_starter import LifecycleStarter


def build_default_lifecycle_starter() -> LifecycleStarter:
    """Composition root for this starter. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_lifecycle_manager()`, and wires it into a
    LifecycleStarter — nothing else.
    """
    return LifecycleStarter(manager=build_default_lifecycle_manager())
