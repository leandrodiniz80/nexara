from app.platform.events.event_executor import PlatformEventExecutor
from app.platform.events.event_manager_factory import build_default_event_manager


def build_default_event_executor() -> PlatformEventExecutor:
    """Composition root for this executor. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_event_manager()`, and wires it into a
    PlatformEventExecutor — nothing else.
    """
    return PlatformEventExecutor(manager=build_default_event_manager())
