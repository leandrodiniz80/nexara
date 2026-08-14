from app.platform.capabilities.capability_executor_factory import (
    build_default_capability_executor,
)
from app.platform.capabilities.platform_capabilities import PlatformCapabilities


def build_default_platform_capabilities() -> PlatformCapabilities:
    """Composition root for this facade. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_capability_executor()`, and wires it into a
    PlatformCapabilities — nothing else.
    """
    return PlatformCapabilities(executor=build_default_capability_executor())
