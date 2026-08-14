from app.platform.events.event_executor_factory import build_default_event_executor
from app.platform.events.platform_events import PlatformEvents


def build_default_platform_events() -> PlatformEvents:
    """Composition root for this facade. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_event_executor()`, and wires it into a PlatformEvents
    — nothing else.
    """
    return PlatformEvents(executor=build_default_event_executor())
