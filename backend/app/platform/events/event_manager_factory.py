from app.platform.events.event_manager import PlatformEventManager
from app.platform.events.event_registry_factory import build_default_event_registry


def build_default_event_manager() -> PlatformEventManager:
    """Composition root for this manager. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_event_registry()`, and wires it into a
    PlatformEventManager — nothing else.
    """
    return PlatformEventManager(registry=build_default_event_registry())
