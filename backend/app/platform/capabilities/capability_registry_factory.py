from app.platform.capabilities.capability_registry import CapabilityRegistry


def build_default_capability_registry() -> CapabilityRegistry:
    """Composition root for this registry. Returns an empty registry — no
    concrete Capability exists yet to register.
    """
    return CapabilityRegistry()
