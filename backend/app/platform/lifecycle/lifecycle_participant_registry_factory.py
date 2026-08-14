from app.platform.lifecycle.lifecycle_participant_registry import LifecycleParticipantRegistry


def build_default_lifecycle_participant_registry() -> LifecycleParticipantRegistry:
    """Composition root for this registry. Returns an empty registry — no
    concrete LifecycleParticipant exists yet to register.
    """
    return LifecycleParticipantRegistry()
