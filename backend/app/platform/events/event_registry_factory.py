from app.platform.events.event_registry import EventRegistry


def build_default_event_registry() -> EventRegistry:
    """Composition root for this registry. Returns an empty registry — no
    concrete PlatformEvent exists yet to register.
    """
    return EventRegistry()
